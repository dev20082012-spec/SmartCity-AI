package org.example.surakshadrishti.controller;

import org.example.surakshadrishti.Service.DetectionService;
import org.example.surakshadrishti.dto.DetectionDTO;
import org.example.surakshadrishti.model.Incident;
import org.example.surakshadrishti.repository.IncidentRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

// controller mess handles whatever api calls
@RestController
@RequestMapping("/api/detections")
@CrossOrigin
public class DetectionController {

    @Autowired
    private DetectionService detectionService;
    @Autowired
    private IncidentRepository incidentRepository;

    // python script posts alerts here hope json isnt broken
    @PostMapping
    public Incident receiveDetection(@RequestBody DetectionDTO dto) {
        return detectionService.saveDetection(dto);
    }

    // returns literally everything in db pls dont spam
    @GetMapping
    public List<Incident> getAllIncidents() {
        return detectionService.getAllIncidents();
    }

    // map polls this constantly every 5 seconds lol
    @GetMapping("/active")
    public List<Incident> getActiveIncidents() {
        return detectionService.getActiveIncidents();
    }

    // click mark resolved button and pray it updates
    @PutMapping("/resolve/{id}")
    public Incident resolveIncident(@PathVariable Long id) {
        return detectionService.resolveIncident(id);
    }

    // threat count for pie chart or something
    @GetMapping("/stats/threats")
    public List<Object[]> threatStats() {
        return incidentRepository.countByThreatType();
    }

    // resolved incidents graveyard
    @GetMapping("/history")
    public List<Incident> history() {
        return incidentRepository.findByStatus("RESOLVED");
    }

}
