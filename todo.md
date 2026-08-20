
## Need to fix!
- [x] If you're a member of an immediate family, that should not be available in the other family groups
- [ ] Don't see a way to clear a selection from the "Also a member of" list (Ctrl to clear!) -> Need a note
- [ ] Rename lines toggle switch to something more meaningful


## UI Improvements
- Do not place labels inside the text input. Do make the label text smaller and horizontally closer to the input. Mute the text slightly.
- Always viewable fields: First Name, Last Name, Sex, Mother, Father, and  Immediate Family Group.
- Add the rest to the Bootstrap Vertical Collapse Component with a heading that says: Additional personal information
- Remove the icon to keep inline with the rest of the fields

Move toggle buttons (View by Generation, Show Group Outlines, Show Connections, Show Between Families) into it's own card heading called View options. Place it above the Actions card.

Add a note (Ctrl-Click to deselect) to the "Also a member of" texting.

Update text "Show Connections" to "Show inter-family lines" 
Update text "Show Between Families" to "Show family-to-family" lines
Update text "Show Group Outlines" to  "Show family borders"

- Improve adding people with required fields and a drop-down for additional fields. Need to review what fields are required.
- Snapping to some kind of grid
- Auto format (left-to-right off birthdays per family)
- General clean up of buttons not needed
- Moving toggle switches
- Stop with the random colors
- Fix color palette


## Improve viewing of Family Groups
Maybe this should be done in layers. Add different layers to hide/view things.
- [x] Intra-family_groups - Hide all the lines within a family
- [x] Box around a family groups
- [ ] Generational divides - Alternating Horizontal Lines to help view generations


## Improving Family Groups - Inheritance
The idea was to automatically link a person to a group when they were assigned a mother or father. There is a problem when a mother/father already have more than one group assigned. There is no way to distinuisgh which of those groups is correct.

- [ ] Can now be added. The first person in the list is the immediate family.


## Fix Generation Button
Added a button to view by generations. It doesn't appear to work


## Relationships
The ability to click on people and see the relationship between them.



## Others
- Spouse - Should we have a link between spouses?
- Add Maiden name. When adding a new female, if she has a spouse and a father, set the maiden name to father's name

## An Admin section
- For a 'super user' to fix simple errors
- for myself to create and assign UUIDs and other


## Admin Tasks
- Split off JS/CSS
- Map how this app works

### Reference
- Color platte: https://gka.github.io/palettes/#/33|d|00429d,96ffea,ffffe0|ffffe0,ff005e,93003a|1|1

