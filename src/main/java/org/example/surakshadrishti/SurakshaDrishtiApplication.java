package org.example.surakshadrishti;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.Query;
import org.springframework.scheduling.annotation.EnableScheduling;

import java.util.List;

@SpringBootApplication
@EnableScheduling


public class SurakshaDrishtiApplication {
    public static void main(String[] args) {
        SpringApplication.run(SurakshaDrishtiApplication.class, args);
    }

}
