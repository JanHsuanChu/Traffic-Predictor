# Workflow Diagram

This diagram defines the goal and architecture of the Traffic-Predictor tool.

```mermaid
flowchart LR
    Database["Database<br/>Congestion-level data<br/>Event-level data"]
    RestAPI["RestAPI<br/>Query the database"]
    DashboardApp["Dashboard App<br/>User picks types of<br/>event to analyze"]
    AI["AI<br/>Analyze the correlation<br/>between traffic and event"]
    Output["Output:<br/>.docx report<br/>with graph"]
    
    Database -->|Query| RestAPI
    RestAPI -->|Data| DashboardApp
    DashboardApp -->|Event selection| AI
    AI -->|Analysis| Output
```

## Pipeline summary

| Stage       | Role |
|------------|------|
| **Database**   | Stores congestion-level and event-level data. |
| **RestAPI**    | Queries the database and exposes data. |
| **Dashboard App** | Lets users choose event types to analyze. |
| **AI**         | Analyzes correlation between traffic and events. |
| **Output**     | Produces a .docx report with graphs. |
