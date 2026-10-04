package org.example.surakshadrishti.model;



import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Entity
@Data
public class Incident {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String cameraId;
    private String threatType;
    private String severity;
    private Double confidence;
    private Double latitude;
    private Double longitude;
    private String colorCode;
    private Integer riskScore;

    private String icon;
    private LocalDateTime createdAt;


    private LocalDateTime timestamp;

    private String status; // ACTIVE, RESOLVED
}
