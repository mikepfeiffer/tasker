// Optional, read-only browser-agent access. Unsupported browsers simply skip this.
// The server still enforces the selected demo account's ownership.
if (document.modelContext?.registerTool) {
  const lifecycle = new AbortController();
  const reportError = () => console.warn('Tasker browser-agent tools are unavailable.');
  try {
    Promise.resolve(document.modelContext.registerTool({
      name: 'read_task_list',
      title: 'Read my tasks',
      description: 'Read tasks belonging to the currently selected Tasker demo account. Does not change tasks or switch accounts.',
      inputSchema: {
        type: 'object',
        properties: { filter: { type: 'string', enum: ['all', 'open', 'completed'] } },
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true, untrustedContentHint: true },
      async execute(input) {
        if (!input || typeof input !== 'object' || Array.isArray(input) ||
            Object.keys(input).some((key) => key !== 'filter') ||
            (input.filter !== undefined && !['all', 'open', 'completed'].includes(input.filter))) {
          throw new Error('Use a filter of all, open, or completed.');
        }
        const response = await fetch('/api/tasks', { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Open Tasker and select a demo account first.');
        const result = await response.json();
        const tasks = result.tasks.filter((task) => !input.filter || input.filter === 'all' ||
          Boolean(task.completed) === (input.filter === 'completed'));
        return { tasks, count: tasks.length };
      },
    }, { signal: lifecycle.signal })).catch(reportError);
  } catch {
    reportError();
  }
  window.addEventListener('pagehide', () => lifecycle.abort(), { once: true });
}
