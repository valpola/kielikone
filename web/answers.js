(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.AnswerMatching = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // What counts as the same answer. Kept in its own module so it can be tested
  // directly: this is the code that decides right from wrong, and a silent change
  // here misgrades every session afterwards.
  //
  // Punctuation and spaces are dropped, so "(birine) teşekkür etmek" can be typed
  // without the brackets — but the frame words themselves are still required. The
  // sb./sth. in the English gloss is what signals that.
  var normalizeAnswer = function (value) {
    return String(value || "")
      .trim()
      .normalize("NFKC")
      .replace(/[().! ,]/g, "")
      .toLocaleLowerCase("tr-TR")
      // circumflex-insensitive: accept a/i/u for â/î/û so learners needn't type the ^
      .replace(/â/g, "a")
      .replace(/î/g, "i")
      .replace(/û/g, "u");
  };

  // Slash-separated alternatives (e.g. "enteresan / ilginç") match in any order,
  // and all of them are required — that is what the "(X / Y)" tip is telling you.
  var normalizeAnswerSet = function (value) {
    return String(value || "")
      .split("/")
      .map(normalizeAnswer)
      .filter(function (part) {
        return part.length > 0;
      })
      .sort()
      .join("/");
  };

  var matches = function (given, expected) {
    return normalizeAnswerSet(given) === normalizeAnswerSet(expected);
  };

  return {
    normalizeAnswer: normalizeAnswer,
    normalizeAnswerSet: normalizeAnswerSet,
    matches: matches,
  };
});
