# Event Check-in System

An integrated event management and data processing system developed for the student-led association 

## 1. Project Overview

This project was developed to streamline participant management, event registration, and attendance tracking for association events.

The system combines a MySQL relational database, a Python-based ETL pipeline, and a QR-code check-in application. It also enables the analysis of participant engagement and event-related statistics.

## 2. Key Features

- Participant Management: Centralized participant database with email-based identification to maintain consistent participant records.

- Event Management: Structured storage of event and registration information.

- ETL Pipeline: Automated extraction, transformation, and loading of data from Google Sheets into MySQL.

- QR Code Check-in: QR-code scanning interface for recording event attendance.

- Data Analysis: Analysis of repeat participation, university and faculty distributions, and event-specific statistics.


## 3. System Architecture

The system follows a data processing workflow:

1. Participant and event information is collected through Google Sheets.

2. The ETL pipeline retrieves and transforms the source data.

3. Processed records are stored in a MySQL relational database.

4. QR codes are generated and distributed to participants.

5. Attendance is recorded through the QR-code check-in application.

6. Attendance data is used for subsequent analysis and reporting.

