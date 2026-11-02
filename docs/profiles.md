# Profiles: the phone's templates

A profile is `profiles/<id>.json`: what the phone shows and what each tile asks. `dhc_edge/profiles.py` loads it, resolves
`extends`, fills in defaults and checks every field; an error names the field (`tiles[2].options: a list of 1-12`). The setup
page lists every profile and marks a broken one with ⚠. The profiles folder is mounted into the container, so a changed
file shows after `{"t": "profile", "profile": "<id>"}` (or Show on the phone, in the setup page), without a rebuild.

The look is atl-phone's Omi Assist tiles: big, high contrast, an icon and a word, the word said when touched. That suits a
wall display and people who see less well; keep it to a handful of tiles per screen.

## The profile

| field | | default |
|---|---|---|
| `id` | letters, digits, `-`, `_` (the file's name) | the file's name |
| `title` | label | the id |
| `description` | label, for the setup page | |
| `style` | `tiles` (big, spoken) or `chips` | `tiles` |
| `columns` | 1–4 | 2 |
| `lang` | `en`, `fr`, `de`: the phone's language unless the edge's `--lang` or the page's `?lang=` say otherwise | `en` |
| `home` | the tiles shown, in order | all, in file order |
| `tiles` | 1–24 tiles | |
| `extends` | another profile's id: its tiles, changed field by field by tiles of the same id here, plus new ones | |
| `drop` | tile ids of the extended profile to leave out | |

A **label** is text, or `{"en": …, "fr": …, "de": …}` (the tests ask for all three in the shipped profiles). A key `"_"`
is ignored: use it for the licence line and a comment.

## A tile

| field | | default |
|---|---|---|
| `id` | its name in events and `state` commands | |
| `label` | label | the id |
| `icon` | an emoji (fonts differ per phone: prefer common ones) | |
| `color` | `blue`, `green`, `yellow`, `red`, `grey` | `blue` |
| `speak` | say its word (and its steps' questions) when touched | true |
| `action` | below | `send` |
| `prompt` | label: the question on its screen (input actions) | its label |

| action | the phone | the event | its own fields |
|---|---|---|---|
| `send` | a tap | `tile` (+ the fixed `data`) | `data` {id: value} |
| `toggle` | shows on/off from its state; a tap asks for the other | `tile` with `value` | |
| `state` | shows its state (`value` + `unit`, and the `label` of the `state` command); a tap asks for news | `tile` | `unit` |
| `say` | says its text on the phone | `tile` | `text` (label) |
| `choice` | the options as tiles; it also shows its state as the option's word (a scene) | `data` {tile: option id} | `options` [{id, label, icon}] (1–12) |
| `number` | big − and + | `data` {tile: n} | `min`, `max`, `step`, `default`, `unit` |
| `scan` | the back camera reads a barcode or QR code (BarcodeDetector, else ZXing); ⌨ to type it | `data` {tile: {code, format}} | `formats` (e.g. `["ean_13", "qr_code"]`), `manual` (true) |
| `photo` | the back camera, a shutter, the photo to keep or take again; with `ocr` the text on it is read and shown to correct | `data` {tile: {jpeg, w, h, text}} | `ocr` (false), `max_px` (1280, 320–1920) |
| `text` | a text box (the keyboard's microphone works too) | `data` {tile: text} | `max` (200, ≤ 500) |
| `steps` | each step's screen in turn, Back and Cancel on each, then a review card (Send) | one `tile` event, `data` {step id: part} | `steps` [1–8 steps], `confirm` (true), `data` |

A **step** has its own `id`, `label` and an action among `choice`, `number`, `scan`, `photo`, `text`, with that action's
fields and `prompt`.

## Making one

1. Copy `blank.json` (or extend one: `cellar.json` and `library.json` are `checkinout.json` with their own words, steps and
   icons).
2. Give each tile an action; chain what belongs to one record into `steps` (one event, so the backend gets it whole).
3. `./test.sh` checks every profile; the setup page shows it and can pretend taps (each step gets a sample answer), so the
   backend's flow can be written before a phone is at hand.
4. Fill what only the backend knows at run time with a `tiles` command: the home's rooms, the cellar's racks, the family's
   names.

```json
{"id": "garden", "title": {"en": "Garden", "fr": "Jardin", "de": "Garten"}, "columns": 2,
 "tiles": [
   {"id": "water", "icon": "💧", "action": "toggle", "label": {"en": "Watering", "fr": "Arrosage", "de": "Bewässerung"}},
   {"id": "plant", "icon": "🌱", "action": "steps", "label": {"en": "New plant", "fr": "Nouvelle plante", "de": "Neue Pflanze"},
    "steps": [{"id": "photo", "action": "photo", "label": {"en": "Photo", "fr": "Photo", "de": "Foto"}},
              {"id": "bed", "action": "choice", "label": {"en": "Bed", "fr": "Massif", "de": "Beet"},
               "options": [{"id": "north", "label": "N"}, {"id": "south", "label": "S"}]}]}]}
```
