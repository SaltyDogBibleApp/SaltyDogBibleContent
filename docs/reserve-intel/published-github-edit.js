// Published article corrections belong in GitHub, not the auth Worker.
// This override intercepts the published-article edit control before the
// legacy Worker-backed handler runs, then opens the live feed in GitHub.
(() => {
  const GITHUB_EDIT_URL =
    "https://github.com/SaltyDogBibleApp/SaltyDogBibleContent/edit/main/reserve-content-feed.json";

  function selectedPublishedArticle() {
    if (typeof state === "undefined" || state.selectedKind !== "published") return null;
    return findItem(state.selectedId, "published");
  }

  function updatePublishedEditCopy() {
    const button = byId("edit-published-button");
    if (button) button.textContent = "Edit in GitHub";

    const note = byId("published-update-note");
    if (note && state?.selectedKind === "published") {
      note.textContent =
        "Published corrections are made in GitHub so the commit and pull-request history remain the source of truth.";
    }
  }

  document.addEventListener(
    "click",
    async (event) => {
      const target = event.target instanceof Element
        ? event.target.closest("#edit-published-button")
        : null;
      if (!target) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      const article = selectedPublishedArticle();
      if (!article) return;

      if (!window.reserveIntelAuth?.isAuthenticated()) {
        showToast("Sign in with GitHub, then select Edit in GitHub again.", "warning");
        return;
      }

      // Open synchronously so Safari does not treat the new tab as a popup.
      window.open(GITHUB_EDIT_URL, "_blank", "noopener,noreferrer");

      try {
        await navigator.clipboard.writeText(article.id);
        showToast(
          `Opened GitHub. Article ID ${article.id} was copied — use it to find this record, then commit on a branch and open a pull request.`,
          "success"
        );
      } catch {
        showToast(
          `Opened GitHub. Search for article ID ${article.id}, then commit on a branch and open a pull request.`,
          "success"
        );
      }

      const note = byId("published-update-note");
      if (note) {
        note.textContent =
          `GitHub opened for ${article.id}. Make the correction there on a branch and open a pull request; do not commit the correction directly to main.`;
      }
    },
    true
  );

  // Keep the published control labeled correctly after article selections rerender it.
  const observer = new MutationObserver(updatePublishedEditCopy);
  const actions = byId("published-update-actions");
  if (actions) observer.observe(actions, {subtree: true, childList: true, characterData: true});
  updatePublishedEditCopy();
})();
