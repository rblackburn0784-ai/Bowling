# Bowling Ball Sprites (v2.8.5a)

The game uses ten visual designs for five gameplay ball types. The actual PNGs
are distributed in **Gutter_Saints_v2.8.5a_Complete_Sprite_Pack.zip**, alongside
The Dude and Jesus approach sprites. Extract the ZIP at the repository root.
No extra rendering library is needed beyond the existing Pillow requirement.

- Hybrid: `hybrid_pink_black.png`, `hybrid_green_black.png`
- Solid: `solid_blue.png`, `solid_red.png`, `solid_orange.png`
- Pearl: `pearl_teal.png`, `pearl_purple.png`
- Urethane: `urethane_blue.png`, `urethane_black.png`
- Plastic: `plastic_cream_black.png`

The actual selected gameplay type comes from `event['ball_key']`. Variant
selection is stable for a given bowler and ball type, so it will not flicker.
The sprite rotates and shrinks along the existing simulated ball path. When
artwork is missing the previous basic circle is used.

The five approach frames play first. The travel sprite appears only after
frame five, when the bowler has released the ball. The existing physics, pin
collisions, scoring, rank and career progression are untouched.
