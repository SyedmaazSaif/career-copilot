// Derive a canonical country name from a free-text job location like
// "Corby, England, United Kingdom" or "USA, Canada, USA timezones".
// Used by the country filter on the jobs screen.

// Most-specific names first; each entry maps a canonical country to the
// spellings that appear in real job-board locations.
const COUNTRY_ALIASES = [
  ["United States", ["united states", "united states of america", "u.s.a", "u.s.", "usa", "us"]],
  ["United Kingdom", ["united kingdom", "great britain", "britain", "england", "scotland", "uk"]],
  ["United Arab Emirates", ["united arab emirates", "uae", "dubai", "abu dhabi"]],
  ["New Zealand", ["new zealand"]],
  ["South Africa", ["south africa"]],
  ["Saudi Arabia", ["saudi arabia", "saudi"]],
  ["Czech Republic", ["czech republic", "czechia"]],
  ["South Korea", ["south korea"]],
  ["Hong Kong", ["hong kong"]],
  ["Sri Lanka", ["sri lanka"]],
  ["Canada", ["canada"]],
  ["Australia", ["new south wales", "australia"]],
  ["Germany", ["germany"]],
  ["France", ["france"]],
  ["India", ["india"]],
  ["Pakistan", ["pakistan"]],
  ["Brazil", ["brazil"]],
  ["Mexico", ["mexico"]],
  ["Spain", ["spain"]],
  ["Italy", ["italy"]],
  ["Netherlands", ["netherlands", "holland"]],
  ["Sweden", ["sweden"]],
  ["Switzerland", ["switzerland"]],
  ["Singapore", ["singapore"]],
  ["Ireland", ["ireland"]],
  ["Poland", ["poland"]],
  ["Portugal", ["portugal"]],
  ["Romania", ["romania"]],
  ["Denmark", ["denmark"]],
  ["Norway", ["norway"]],
  ["Finland", ["finland"]],
  ["Belgium", ["belgium"]],
  ["Austria", ["austria"]],
  ["Turkey", ["turkey"]],
  ["Japan", ["japan"]],
  ["China", ["china"]],
  ["Indonesia", ["indonesia"]],
  ["Malaysia", ["malaysia"]],
  ["Thailand", ["thailand"]],
  ["Vietnam", ["vietnam"]],
  ["Philippines", ["philippines"]],
  ["Egypt", ["egypt"]],
  ["Nigeria", ["nigeria"]],
  ["Kenya", ["kenya"]],
  ["Argentina", ["argentina"]],
  ["Chile", ["chile"]],
  ["Colombia", ["colombia"]],
  ["Israel", ["israel"]],
  ["Ukraine", ["ukraine"]],
  ["Greece", ["greece"]],
  ["Estonia", ["estonia"]],
  ["Latvia", ["latvia"]],
  ["Lithuania", ["lithuania"]],
  ["Croatia", ["croatia"]],
  ["Bulgaria", ["bulgaria"]],
  ["Hungary", ["hungary"]],
  ["Russia", ["russia"]],
];

const _ALIAS_RE = COUNTRY_ALIASES.map(([name, aliases]) => {
  const joined = aliases
    .slice()
    .sort((a, b) => b.length - a.length) // longest alias first within a country
    .map((a) => a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  return [name, new RegExp(`(^|[^a-z])(${joined})($|[^a-z])`)];
});

export function countryOf(location) {
  if (!location) return "";
  const s = (location || "").toLowerCase();
  for (const [name, re] of _ALIAS_RE) {
    if (re.test(s)) return name;
  }
  return "";
}
