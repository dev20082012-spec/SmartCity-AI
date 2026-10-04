package org.example.surakshadrishti.dto;

import lombok.Data;


    @Data
    public class DetectionDTO {
        private String cameraId;
        private String threatType;
        private String severity;
        private Double confidence;
        private Double latitude;
        private Double longitude;

    }


