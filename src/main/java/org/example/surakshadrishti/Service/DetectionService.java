package org.example.surakshadrishti.Service;

import org.example.surakshadrishti.dto.DetectionDTO;
import org.example.surakshadrishti.model.Incident;
import org.example.surakshadrishti.repository.IncidentRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

// big service class with logic everywhere
@Service
public class DetectionService {

    @Autowired
    private IncidentRepository incidentRepository;

    // saves detection from python script
    public Incident saveDetection(DetectionDTO dto) {
        Incident incident = new Incident();

        incident.setCameraId(dto.getCameraId());
        incident.setThreatType(dto.getThreatType());
        incident.setConfidence(dto.getConfidence());
        incident.setTimestamp(LocalDateTime.now());
        incident.setStatus("ACTIVE");
        incident.setLatitude(dto.getLatitude());
        incident.setLongitude(dto.getLongitude());
        incident.setIcon(getIconForThreat(dto.getThreatType()));
        incident.setRiskScore(calculateRiskScore(dto));

        String finalSeverity = adjustSeverity(dto.getSeverity(), incident.getRiskScore());
        incident.setSeverity(finalSeverity);
        incident.setColorCode(getColorForSeverity(finalSeverity));
        incident.setCreatedAt(LocalDateTime.now());
        
        // if in high risk box then make it critical right away lol
        if (isHighRiskZone(dto.getLatitude(), dto.getLongitude())) {
            incident.setSeverity("CRITICAL");
        }

        return incidentRepository.save(incident);
    }

    public List<Incident> getAllIncidents() {
        return incidentRepository.findAll();
    }

    public List<Incident> getActiveIncidents() {
        return incidentRepository.findByStatus("ACTIVE");
    }

    // hope id exists or runtime error boom
    public Incident resolveIncident(Long id) {
        Incident incident = incidentRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Incident not found"));

        incident.setStatus("RESOLVED");
        return incidentRepository.save(incident);
    }

    // color mapping helper whatever
    private String getColorForSeverity(String severity) {
        return switch (severity.toUpperCase()) {
            case "LOW" -> "GREEN";
            case "MEDIUM" -> "YELLOW";
            case "HIGH" -> "ORANGE";
            case "CRITICAL" -> "RED";
            default -> "GRAY";
        };
    }

    // returns icon name string for map frontend
    private String getIconForThreat(String threatType) {
        return switch (threatType.toUpperCase()) {
            case "FIRE" -> "fire_icon";
            case "FIGHT" -> "violence_icon";
            case "CROWD_PANIC" -> "crowd_icon";
            case "MEDICAL" -> "medical_icon";
            case "SUSPICIOUS_OBJECT" -> "alert_icon";
            case "TRAFFIC_VIOLATION" -> "traffic_icon";
            default -> "default_icon";
        };
    }

    // math for risk score based on threat types
    private int calculateRiskScore(DetectionDTO dto) {
        int base = switch (dto.getThreatType().toUpperCase()) {
            case "FIRE" -> 90;
            case "FIGHT" -> 75;
            case "CROWD_PANIC" -> 85;
            case "MEDICAL" -> 80;
            case "SUSPICIOUS_OBJECT" -> 70;
            default -> 50;
        };

        // boost score with confidence
        int confidenceBoost = (int) (dto.getConfidence() * 10);
        return Math.min(base + confidenceBoost, 100);
    }

    // clamp severity tiers
    private String adjustSeverity(String originalSeverity, int riskScore) {
        if (riskScore >= 90) return "CRITICAL";
        if (riskScore >= 70) return "HIGH";
        if (riskScore >= 50) return "MEDIUM";
        return "LOW";
    }

    // runs every 60 seconds to yell at unresolved incidents
    @Scheduled(fixedRate = 60000)
    public void escalateIncidents() {
        List<Incident> active = incidentRepository.findByStatus("ACTIVE");

        for (Incident i : active) {

            // if time is missing just set it now so duration doesn't throw null
            if (i.getCreatedAt() == null) {
                i.setCreatedAt(LocalDateTime.now());
                incidentRepository.save(i);
                continue;
            }

            long minutes = Duration.between(i.getCreatedAt(), LocalDateTime.now()).toMinutes();

            String newSeverity = i.getSeverity();

            // old incidents become critical if nobody attends to them haha
            if (minutes > 10) newSeverity = "CRITICAL";
            else if (minutes > 5) newSeverity = "HIGH";

            if (!newSeverity.equals(i.getSeverity())) {
                i.setSeverity(newSeverity);
                i.setColorCode(getColorForSeverity(newSeverity));
                incidentRepository.save(i);
            }
        }
    }

    // hardcoded bounding box for some sensitive area in delhi
    private boolean isHighRiskZone(double lat, double lon) {
        return lat > 28.60 && lat < 28.65 && lon > 77.18 && lon < 77.23;
    }

}
