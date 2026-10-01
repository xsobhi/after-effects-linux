// Wine Gecko (the IE engine used by Adobe's sign-in window) takes form-control colours
// from the Windows system palette. With a dark desktop palette, web pages that only set
// a dark text colour get unreadable fields, so keep web content on standard light colours.
pref("ui.-moz-field", "#ffffff");
pref("ui.-moz-fieldtext", "#000000");
pref("ui.-moz-combobox", "#ffffff");
pref("ui.-moz-comboboxtext", "#000000");
pref("ui.buttonface", "#efefef");
pref("ui.buttontext", "#000000");
pref("ui.-moz-buttonhoverface", "#e5e5e5");
pref("ui.-moz-buttonhovertext", "#000000");
pref("ui.window", "#ffffff");
pref("ui.windowtext", "#000000");
pref("ui.-moz-dialog", "#f0f0f0");
pref("ui.-moz-dialogtext", "#000000");
pref("ui.graytext", "#6d6d6d");
pref("ui.threedface", "#efefef");
pref("ui.threedshadow", "#a0a0a0");
pref("ui.threedhighlight", "#ffffff");
pref("ui.threeddarkshadow", "#696969");
pref("ui.threedlightshadow", "#e3e3e3");
// Pages that name no font get a sans face, as the sign-in page expects.
pref("font.default.x-western", "sans-serif");
