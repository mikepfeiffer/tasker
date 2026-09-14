// Small, optional conveniences. Adding, filtering, completing, and exporting also work without JS.
const accountMenu = document.querySelector('.account-menu');
document.addEventListener('click', (event) => {
  if (accountMenu && !accountMenu.contains(event.target)) accountMenu.open = false;
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && accountMenu?.open) {
    accountMenu.open = false;
    accountMenu.querySelector('summary').focus();
  }
});
document.querySelectorAll('.dismiss-notice').forEach((button) => {
  button.addEventListener('click', () => button.closest('.notice').remove());
});
// Reject whitespace-only names before submitting, matching the server's validation.
const titleInput = document.querySelector('#task-title');
titleInput?.addEventListener('input', () => {
  titleInput.setCustomValidity(
    titleInput.value.trim() ? '' : 'Please enter a task name.',
  );
});
