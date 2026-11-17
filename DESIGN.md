# Fallout 1in2 Objectives — design

A quest and loot helper for Fallout 1in2 (Fallout 1 in the Fallout 2 engine, sfall 4.5), played on PC.
Installed as a removable mod in `Fallout1in2/mods/` (its own folder, listed in `mods_order.txt`).

## 1. Right-hand panel (always on)

Small Pip-Boy-green text on the right edge of the map screen, hidden in menus, dialogue and combat menus.

```
 MAIN QUEST                       Water: 112 days
  Find the water chip
   X Talk to the Overseer
     Go to Vault 15                east of Shady Sands
     Find the water chip                    (not here)

 OPTIONAL
  Shady Sands: radscorpions
     Talk to Seth at the gate        14 hexes NE  ^
     Kill the radscorpions                  (2/5)

 GEAR  Hunting Rifle (better)          8 hexes W
```

- Main quest first, then optional quests in their own section.
- Each quest shows its exact next steps. Done steps get an X, then drop off.
- Steps on the current map show hex distance and an arrow. Other steps say which location to go to.
- The water-chip deadline is shown (and later the Mutant invasion timer).
- How many optional quests show is a setting (default 3: the tracked one plus the nearest ones).

## 2. Objectives tab (opened with a key, default `O`)

A full-screen window, Pip-Boy style, with three pages:

- **Quests**: main quest, then optional quests grouped by town. Each quest lists all its steps with
  status, where to go, who to talk to, what to bring. Track button: pins the quest to the top of the panel.
  Finished and failed quests in a collapsed list.
- **Gear**: weapons and armor on the current map (and known in visited places) that beat what you use,
  nearest first, with where they are (ground, container, carried by someone, sold by a merchant) and the
  distance. Get-it button: the panel and the outline lead you to it.
- **Settings**: panel on/off, position and number of quests; highlight on/off and colours; spoiler level;
  key bindings.

## 3. Highlights on the map

Using sfall outlines (same mechanism as the built-in Ctrl highlighter):

- Quest items: yellow.
- Weapons and armor better than what you have equipped: green.
- Optional: containers holding either of those.
- Always on (no Motion Sensor needed); can be switched off in Settings.

"Better" weapon: damage per action point against your current weapon, with your skills, ammo you carry,
and Strength requirement taken into account. "Better" armor: AC plus damage threshold/resistance for normal
damage.

## 4. Data and how it is built

- `quests.txt` + `PIPBOY.msg` (`mods/fo1_base`): every Pip-Boy quest, its location and the global variable
  (GVAR) that tracks it, with the values for "show" and "done".
- `Vault13.gam`: names of all global variables.
- The Fo1in2 script sources (rotators/Fo1in2 on GitHub, scripts folder only): which dialogue, kill or item
  moves each GVAR, so each quest gets exact steps with tick-off conditions.
- Item protos (`proto/items`) for weapon/armor stats; maps (`maps/*.MAP`) for where items and people are.
- A Python build tool turns this into one data file the in-game script reads, like the Morrowind tools.
  Steps are generated first, then hand-checked for the main quest and each town.

## 5. Build and test

- Script written in SSL, compiled to `.int` with sfall's compiler (run through Wine).
- Offline checks of the data (every step's condition refers to a real GVAR / item / critter).
- In-game check on a save before each release.

## 6. Order of work

1. Data tools: quests, GVARs, steps for Vault 13, Shady Sands, Vault 15, Junktown.
2. Panel with tick-offs and distances; water-chip timer.
3. Highlights (quest items, better gear).
4. Objectives tab: Quests page, then Gear, then Settings.
5. Steps for the remaining towns (Hub, Necropolis, Brotherhood, Boneyard, Glow, Mariposa, Cathedral).

## Open questions

- Spoiler level: exact steps everywhere (chosen), or a setting to hide solutions to puzzles?
- Key for the tab: `O`? (Fallout 2 engine doesn't use it.)
