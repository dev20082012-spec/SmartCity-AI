package org.example.surakshadrishti.repository;



import org.example.surakshadrishti.model.Incident;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface IncidentRepository extends JpaRepository<Incident, Long> {
    List<Incident> findByStatus(String status);
    @Query("SELECT i.threatType, COUNT(i) FROM Incident i GROUP BY i.threatType")
    List<Object[]> countByThreatType();

}
