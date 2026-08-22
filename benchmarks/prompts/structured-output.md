You are a structured-output agent. Return JSON only. Do not add Markdown or explanatory text.

Convert this text into the required schema:

"Task 184 is blocked because the shipping API credentials are missing. Owner is Anna. Priority is high. The next action is to request credentials from operations."

Required schema:
{
  "task_id": 0,
  "status": "open|blocked|done",
  "owner": "...",
  "priority": "low|medium|high",
  "next_action": "..."
}
