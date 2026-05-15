# FRIDAY Showcase Scenarios

These scenarios describe what FRIDAY is designed to do in the private Windows runtime. They are written as product examples, not as exposed source-code instructions.

<div align="center">
<img src="images/interaction-loop.svg" width="860" alt="FRIDAY interaction loop"/>
</div>

---

## Daily Desktop Flow

User:

```text
Open Spotify, play something calm, and set the volume to 20 percent.
```

FRIDAY can route the request to desktop tools, open the relevant app or service, adjust media behavior, and confirm only after the action path has run.

---

## File-Aware Reasoning

User drops a document into the UI and asks:

```text
Summarize the parts that matter for the launch plan.
```

FRIDAY extracts relevant text chunks, avoids sending unnecessary content, and answers with context from the file plus the user's project memory.

---

## Proactive Memory

User:

```text
What were we trying to fix last time in the FRIDAY voice pipeline?
```

FRIDAY can consult recent session history, long-term memory, and narrative tracking to reconstruct the thread instead of treating the question as stateless.

---

## Debugging and Deep Reasoning

User:

```text
This error keeps happening when the voice loop starts. Analyze the likely cause.
```

FRIDAY can route the request to a deeper reasoning model, use project context, inspect relevant logs when available, and return an actionable diagnosis.

---

## User-State Adaptation

If the user is moving quickly, correcting often, or asking short command-like messages, FRIDAY can reduce verbosity and prioritize action.

If the user is exploring a complex design decision, FRIDAY can shift into a more reflective planning mode.

---

## Boundaries

The public showcase does not expose the private runtime's prompts, automation code, personal memory, or credentials. These scenarios explain the product behavior at a safe level.
