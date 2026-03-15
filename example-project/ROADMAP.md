# ROADMAP.md

## Project Goal

Build a small internal web application for collecting, triaging, and tracking product feedback from employees.

The app should let employees submit feedback items, let product managers classify them, and let leadership view a simple dashboard of status by category.

## Target User

- Employee submitting product feedback
- Product manager triaging feedback
- Leadership viewing summary counts and progress

## Ordered Milestones

### Milestone 1 - Feedback Submission

Implement a form where employees can create feedback items with:

- title
- description
- category
- priority hint
- reporter email

Users must be able to submit and then view the created record.

### Milestone 2 - Triage Workflow

Add product-manager actions for:

- changing status
- assigning owner
- adding internal notes
- filtering feedback list by status and category

### Milestone 3 - Dashboard

Add a simple dashboard that shows:

- total feedback count
- counts by status
- counts by category
- list of newest untriaged items

## In Scope

- server-rendered web UI
- SQLite persistence
- CRUD for feedback items
- triage status updates
- dashboard summary view
- automated tests for core flows

## Out of Scope

- SSO
- file uploads
- background jobs
- external analytics
- multi-tenant support

## Acceptance Criteria

### Milestone 1

- a user can submit feedback through the web form
- invalid submissions show validation errors
- submitted feedback is stored in SQLite

### Milestone 2

- a manager can update status and owner
- the feedback list can be filtered by status and category

### Milestone 3

- dashboard counts match database contents
- newest untriaged items are shown in descending creation order
