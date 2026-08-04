## Questions
- How to define a "Group"? A husband/wife or single can be a spouse group. A person can belong to two groups. I have my family. I am part of my father/mother family.



## Improvemnts
- Find relationships between nodes. Great Grand Uncle 4 times removed.
- How to show generations? Horizontal bands?
- Snap for better vertical alignment?
- Auto format (left-to-right off birthdays per family)
- User/Pass -> Family Name and some password
- Save to DB -> also save locations

## Reference
- Color platte: https://gka.github.io/palettes/#/33|d|00429d,96ffea,ffffe0|ffffe0,ff005e,93003a|1|1


## Pocketbase Schema
treeFamilies — code (text, unique), name (text)
treePeople — family (relation → treeFamilies), name (text), sex (select: male/female), birthday (date), place_of_birth (text), current_location (text), family_groups (JSON)
treeRelationships — family (relation → treeFamilies), source (relation → treePeople), target (relation → treePeople), relation (select: father/mother)
treePositions — family (relation → treeFamilies), person (relation → treePeople), x (number), y (number)
treeGroups — family (relation → treeFamilies), number (number), label (text), color (text — store the hex value so you can override the random assignment if desired)

## Security-ish
PocketBase's API is publicly accessible by default, meaning someone could technically query treeFamilies and brute-force codes if they're short and predictable. To mitigate this you'd want codes to be long enough to be impractical to guess — something like 12 random alphanumeric characters — and you could set PocketBase API rules on treeFamilies to only allow lookups where the code matches exactly, rate-limiting through PocketBase's own rule system or a reverse proxy like Caddy or Nginx in front of it.