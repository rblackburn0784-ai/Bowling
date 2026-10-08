from dataclasses import dataclass

@dataclass(slots=True)
class Bowler:
    id: int | None
    name: str
    owner_id: int
    handedness: str = "R"
    rank: int = 1
    accuracy: int = 20
    style: int = 10
    flair: int = 10
    consistency: int = 20
    spin: int = 10
    nerves: int = 10
    team_name: str | None = None
    sprite_key: str | None = None

    @property
    def stat_total(self):
        return self.accuracy+self.style+self.flair+self.consistency+self.spin+self.nerves
