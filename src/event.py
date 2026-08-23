class Event:
    def __init__(self, time: float, before_note: bool, property: str, amount: float):
        self._time = time
        self._before_note = before_note
        self._property = property
        self._amount = amount

    def time(self) -> float:
        return self._time

    def before_note(self) -> bool:
        return self._before_note

    def property(self) -> str:
        return self._property

    def amount(self) -> float:
        return self._amount
