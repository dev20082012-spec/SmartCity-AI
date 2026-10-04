package org.example.surakshadrishti.controller;




import org.example.surakshadrishti.Service.DetectionService;
import org.example.surakshadrishti.dto.DetectionDTO;
import org.example.surakshadrishti.model.Incident;
import org.example.surakshadrishti.repository.IncidentRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/detections")
@CrossOrigin
public class DetectionController {

    @Autowired
    private DetectionService detectionService;
    @Autowired
    private IncidentRepository incidentRepository;
    @PostMapping
    public Incident receiveDetection(@RequestBody DetectionDTO dto) {
        return detectionService.saveDetection(dto);
    }
    @GetMapping
    public
    List<Incident> getAllIncidents() {
        return detectionService.getAllIncidents();
    }

    @GetMapping("/active")
    public List<Incident> getActiveIncidents() {
        return detectionService.getActiveIncidents();
    }
    @PutMapping("/resolve/{id}")
    public Incident resolveIncident(@PathVariable Long id) {
        return detectionService.resolveIncident(id);
    }
    @GetMapping("/stats/threats")
    public List<Object[]> threatStats() {
        return incidentRepository.countByThreatType();
    }
    @GetMapping("/history")
    public List<Incident> history() {
        return incidentRepository.findByStatus("RESOLVED");
    }

}
