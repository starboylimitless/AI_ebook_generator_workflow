# Ebook Generator Workflow Documentation

This document provides a technical overview of the Ebook Generator Workflow, detailing its architecture, tools, libraries, and how it compares to standard automation frameworks.

## 1. Core Architecture: Hierarchical Multi-Agent Pipeline

The system is built as a **custom hierarchical agentic workflow** written entirely in Python. It does not rely on high-level frameworks like Crew.ai or n8n, allowing for maximum control and optimizations (like custom caching and state-aware retries).

### The Orchestrator: `MasterAgent`
At the top level, the `MasterAgent` acts as the project manager. It:
- **Maintains State**: Coordinates the flow of data between specialized agents.
- **Dependency Management**: Ensures Agent B only runs after Agent A completes successfully.
- **Quality Verification Loop**: Automatically verifies output quality (e.g., TOC consistency) and re-runs parts of the pipeline if checks fail.
- **Cost Controls**: Managed "Safe Credit Mode" and image caching to minimize API usage.

### Specialized Agents
Every agent inherits from a `BaseAgent` class, providing a standardized way to handle LLM calls, logging, and error handling:
- **DocumentStructureAgent**: Extracts semantic hierarchy (chapters/sections) from raw text.
- **VisualLayoutAgent**: Analyzes reference PDFs to extract design tokens (margins, spacings, font sizes).
- **ImageSemanticAgent**: Identifies "high value" spots for visual assets.
- **OpenAIImageAgent**: Communicates with DALL-E 3 to generate optimized visuals.
- **AlignmentAgent**: Maps planned content into the final visual slots.
- **FinalOptimizationAgent**: Uses **ReportLab** to programmatically generate the final 32MB PDF.

## 2. Tools & Libraries

| Library | Purpose |
| :--- | :--- |
| **OpenAI (GPT-4o & DALL-E 3)** | Intellectual heavy-lifting, text normalization, and image generation. |
| **ReportLab** | Professional-grade PDF generation (the "Engine" that builds the actual book). |
| **pypdf / pdfminer.six** | High-fidelity text and layout extraction from source PDFs. |
| **Pillow (PIL)** | Image processing and asset optimization. |
| **python-dotenv** | Secure management of API keys and environment variables. |

## 3. Framework Comparisons

### Comparison to Crew.ai
While we don't use the `crewai` library, the workflow follows very similar patterns:
- **Role-Based**: Each agent has a specific "Backstory" (defined in prompt files) and a specific "Goal" (extracting structure, planning images).
- **Sequential & Hierarchical**: The `MasterAgent` functions exactly like a Crew.ai `Manager`, making decisions on when to verify or retry tasks.
- **Independence**: Agents are decoupled; they only communicate via standardized JSON "handoffs."

### Comparison to n8n
The workflow shares functional similarities with n8n:
- **Node-Based Flow**: Each agent represents a functional node.
- **JSON Payload Passing**: Just like n8n's data structure, each step in our pipeline transforms a JSON object and passes it to the next.
- **Error Handling**: The `BaseAgent` retry logic is analogous to n8n's "On Error" node configurations.

## 4. Key Innovation: Caching & Verification
Unlike generic workflows, this system includes:
- **Prompt-Based Image Caching**: Before calling DALL-E 3, the system hashes the prompt and checks the `output` directory for a matching asset. If found, it skips the expensive API call.
- **Semantic Validation**: The `MasterAgent` parses the generated metadata to ensure logical consistency (e.g., ensuring every TOC item exists in the chapter list).

## 5. Portability: Can we use this in Crew.ai or n8n?

**Yes.** The current architecture was designed with modularity in mind, making it highly portable to external frameworks.

### Integration with Crew.ai
To migrate this code to [Crew.ai](https://www.crewai.com/), you would:
1. **Convert Agents to 'Tools' or 'Tasks'**: Each specialized agent (e.g., `DocumentStructureAgent`) can be wrapped as a custom `Tool` that the Crew.ai agent calls, or its `run()` logic can be defined as the `Task` itself.
2. **Use the MasterAgent as a 'Manager'**: The orchestration logic in `MasterAgent` (the sequence of steps and verification loops) can be handled by a Crew.ai `Manager` agent or by defining a `Crew` with a `Process.sequential` flow.
3. **Prompt Migration**: The existing `.txt` prompt files can be directly passed into the `Agent(backstory=..., goal=...)` definitions.

### Integration with n8n
To migrate this code to [n8n](https://n8n.io/), you would:
1. **Custom Python Code Nodes**: n8n allows running Python scripts. You can import our agent classes into an n8n "Code" node.
2. **Standardized JSON Handoffs**: Since each agent communicates via JSON files (e.g., `structured_document.json`), you can use n8n's native JSON handling to pass output from one "Agent Node" to the next.
3. **Execution Control**: n8n's visual canvas would replace the `MasterAgent`'s loop, allowing you to see the "Pipeline" and "Retries" visually.

## 6. Frequently Asked Questions (FAQ)

### Q: Does n8n automatically create nodes from my code?
**No.** n8n does not "scan" a Python repository to build a workflow. You must manually:
1. Drag a "Code" node onto the canvas.
2. Paste the relevant Python logic (or call a script).
3. Connect it to the next node.
Think of n8n as a "Visual Script Runner" - you still have to build the flow.

### Q: Why would we switch to Crew.ai?
**Use Crew.ai if:** You want your agents to have "conversations" or autonomy to change the plan dynamically (e.g., "This chapter is confusing, let me research more examples first").
**Stick with current code if:** You need a predictable, fast, and cost-effective pipeline (Step 1 -> Step 2 -> Step 3).

### Q: Why would we switch to n8n?
**Use n8n if:** You want to attach this eBook generator to a website, email trigger, or payment system (e.g., "When user pays on Stripe -> Generate eBook -> Email PDF").
**Stick with current code if:** You are running this locally on your machine or a single server.
