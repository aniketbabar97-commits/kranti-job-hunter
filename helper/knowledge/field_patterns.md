# Label -> field patterns, answer strategy, confirmation / already-applied detection

## Label regexes (EN, from PS12007 selectors.js; facts) plus DE equivalents (ours, since no repo had DE maps)
| key | EN | DE |
|---|---|---|
| firstName | `^(legal )?(first|given) name` | `^vorname` |
| lastName | `^(legal )?(last|family) name|^surname` | `^(nach|familien)name` |
| email | `^e-?mail` | `e-?mail` |
| phone | `^phone number|mobile|telephone` | `telefon|mobil|handy|rufnummer` |
| phoneType | `phone device type|phone type` | `gerätetyp|telefontyp` |
| country | `^country(\s*/\s*(territory|region))?$` | `^land` |
| state | `^(state|province|region|county)` | `bundesland|region` |
| city | `^(city|town|municipality)` | `^(ort|stadt|wohnort)` |
| postal | `^(postal|zip|post) ?code` | `postleitzahl|plz` |
| address1 | `^address line 1|^street` | `straße|strasse|anschrift|adresse` |
| source | `how did you hear` | `wie (haben|sind) sie .*(erfahren|aufmerksam)|quelle` |
| previousWorker | `previously (worked|been employed)|former (employee|worker)|worked (here|for us) before` | `bereits .*(gearbeitet|beschäftigt)|ehemalige?r? mitarbeiter` |
| linkedin | `linkedin` | same |
| salary | `salary|compensation|pay expectation` | `gehalt(svorstellung)?|vergütung|jahresbrutto` |
| notice | `notice period` | `kündigungsfrist` |
| startDate | `earliest start|available to start` | `eintrittstermin|verfügbar ab|frühestmöglich` |
| sponsorship | `sponsor` (and `without\b.{0,40}sponsor` inverts) | `visum|arbeitserlaubnis.*(benötigen|erforderlich)` |
| workAuth | `(authori[sz]ed|eligible|permitted|legally able)\s+to\s+work|work\s+authori[sz]ation|right\s+to\s+work|work\s+permit` | `arbeitserlaubnis|aufenthaltstitel|berechtigt.*arbeiten` |
| relocate | `relocat` | `umzug|umzugsbereit` |
| resume | `resume|\bcv\b` | `lebenslauf|cv` |
| coverLetter | `cover letter` | `anschreiben|motivationsschreiben` |
| gender | `^gender|^sex\b` | `geschlecht|anrede` |
| degree | `^degree` | `abschluss` |

## Answer strategy (consensus across Amro212, tso_autofiller, PS12007, PINGx969)
- Saved per-question answers come first. Then built-in pattern rules. Then (optionally) an LLM. Then leave the field for a human. Never guess EEO or disclosure answers: use the profile value or the "decline" option.
- Option matching: exact match (case- and space-normalised), then synonym groups (degree: Bachelor's/BSc/B.Sc/Bachelor of Science...; Master's/MSc/M.Sc; Mobile/Cell/Mobiltelefon), then contains in either direction. Reject the match if more than one option matches.
- Placeholder detection for "nothing selected": `^(-+\s*)?((please )?(select|choose|pick)\b.{0,30}|-+|none selected|)(\s*-+)?$`. DE: `bitte (wählen|auswählen)`. FR: `sélectionner`.
- Preserve existing answers. If a radio group already has a choice, do not change it (tso_autofiller).
- Validate after Next: read `[role=alert]` and the ATS-specific error nodes, then map each error back to its field container.
- Safety: block clicks on any element matching `^(submit|submit application|apply|send application|absenden|bewerbung (absenden|senden))$` unless you are in an explicit submit step.

## Confirmation-page strings
- EN: "thank you for applying", "thank you for your application", "application submitted", "application has been submitted", "application received", "your application has been received", "we have received your application", "Congratulations" (Workday dialog).
- DE (ours): "vielen dank für ihre bewerbung", "bewerbung (wurde )?(erfolgreich )?(eingereicht|versendet|übermittelt)", "wir haben ihre bewerbung erhalten", "eingangsbestätigung".
- Structural: Greenhouse `.confirmation__content` or URL `/confirmation`. Lever URL `/thanks`. Ashby `[class*=application-form-success-container]`. Workday review step is gone and a "Submitted" label appears.

## Already-applied detection
- Strings: "already applied", "you have already applied", "you('ve| have) already applied", "Applied X days ago" (LinkedIn), Workday "You've already applied for this job" or candidate home status "Submitted"/"In Review". DE: "bereits beworben", "sie haben sich bereits", "bewerbung liegt bereits vor".
- Local dedupe: VelvetOverride keeps a SQLite table keyed on normalised job id plus URL (`is_already_applied(url, job_id)`). PS12007 uses the Workday req id (`_((?:J?R|REQ|JR)[-_]?\d[\w-]*)$` from the URL slug) to spot duplicates across sites.
