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

@Service
public class DetectionService {

    @Autowired
    private IncidentRepository incidentRepository;

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

    public Incident resolveIncident(Long id) {
        Incident incident = incidentRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Incident not found"));

        incident.setStatus("RESOLVED");
        return incidentRepository.save(incident);
    }

    private String getColorForSeverity(String severity) {
        return switch (severity.toUpperCase()) {
            case "LOW" -> "GREEN";
            case "MEDIUM" -> "YELLOW";
            case "HIGH" -> "ORANGE";
            case "CRITICAL" -> "RED";
            default -> "GRAY";
        };
    }

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

    private int calculateRiskScore(DetectionDTO dto) {
        int base = switch (dto.getThreatType().toUpperCase()) {
            case "FIRE" -> 90;
            case "FIGHT" -> 75;
            case "CROWD_PANIC" -> 85;
            case "MEDICAL" -> 80;
            case "SUSPICIOUS_OBJECT" -> 70;
            default -> 50;
        };

        int confidenceBoost = (int) (dto.getConfidence() * 10);
        return Math.min(base + confidenceBoost, 100);
    }

    private String adjustSeverity(String originalSeverity, int riskScore) {
        if (riskScore >= 90) return "CRITICAL";
        if (riskScore >= 70) return "HIGH";
        if (riskScore >= 50) return "MEDIUM";
        return "LOW";
    }

    // 🚨 AUTO ESCALATION ENGINE
    @Scheduled(fixedRate = 60000)
    @Scheduled(fixedRate = 60000)
    public void escalateIncidents() {
        List<Incident> active = incidentRepository.findByStatus("ACTIVE");

        for (Incident i : active) {

            // 🛑 Skip incidents with no creation time
            if (i.getCreatedAt() == null) {
                i.setCreatedAt(LocalDateTime.now());
                incidentRepository.save(i);
                continue;
            }

            long minutes = Duration.between(i.getCreatedAt(), LocalDateTime.now()).toMinutes();

            String newSeverity = i.getSeverity();

            if (minutes > 10) newSeverity = "CRITICAL";
            else if (minutes > 5) newSeverity = "HIGH";

            if (!newSeverity.equals(i.getSeverity())) {
                i.setSeverity(newSeverity);
                i.setColorCode(getColorForSeverity(newSeverity));
                incidentRepository.save(i);
            }
        }
    }

    private boolean isHighRiskZone(double lat, double lon) {
        return lat > 28.60 && lat < 28.65 && lon > 77.18 && lon < 77.23;
    }

}
