from bpy.types import Object


class Effector:
    """
    An effector object.

    - `object`: the effector's object
    - `move_duration`: the allowed move duration of the effector (in seconds)
    - `return_duration`: the allowed return duration of the effector (in seconds)
    - `lift_amount`: the unit lift amount of the effector
    """

    def __init__(
        self,
        object: Object,
        move_duration: float,
        return_duration: float,
        lift_amount: float,
    ):
        self._object = object
        self._move_duration = move_duration
        self._return_duration = return_duration
        self._lift_amount = lift_amount

    def object(self) -> Object:
        """
        Returns the effector's object.
        """

        return self._object

    def move_duration(self) -> float:
        """
        Returns the move duration of the effector in seconds.
        """

        return self._move_duration

    def return_duration(self) -> float:
        """
        Returns the return duration of the effector in seconds.
        """

        return self._return_duration

    def lift_amount(self) -> float:
        """
        Returns the unit lift amount of the effector.
        """

        return self._lift_amount
