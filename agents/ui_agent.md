# UI/CLI Agent

## Role
The UI Agent serves as the bridge between the user and the system, processing commands and visualizing the internal state.

## Responsibilities
- Implementing the interactive CLI loop for `index`, `search`, and `status` commands.
- Initializing the background worker threads.
- Reporting real-time system metrics such as queue depth and total pages indexed.

## Prompt Used
"You are a UI Design agent. Create an interactive Command Line Interface for the web crawler. 
When the user types 'status', display the current queue depth (back pressure status) and the count of unique visited URLs. 
Launch 5 daemon threads at startup to handle background indexing. 
Provide clear feedback for invalid commands and ensure the 'exit' command stops the system cleanly."