// Prompt before an accidental close/reload so unsaved labels aren't lost.
window.onbeforeunload = function () {
    return "Leave the app? Unsaved labels will be lost.";
};
