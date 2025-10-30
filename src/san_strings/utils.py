import math
from functools import cache

import chess


def _sliding_delta(s1: chess.Square, s2: chess.Square) -> int:
    """
    Get the delta of the index in `chess.SQUARES` required to move
    one step from `s1` toward `s2`. Raises `AssertionError` if `s1`
    and `s2` are not on the same file, rank, or diagonal.

    >>> _sliding_delta(chess.C3, chess.F6)
    9
    >>> chess.C3 + 9 == chess.D4
    True
    """
    assert s1 != s2, 's1 and s2 must be different squares'

    x_delta = chess.square_file(s2) - chess.square_file(s1)
    y_delta = chess.square_rank(s2) - chess.square_rank(s1)

    assert 0 in (x_delta, y_delta) or abs(x_delta) == abs(y_delta), (
        's1 and s2 must be on the same file, rank, or diagonal; got '
        f'{chess.square_name(s1)} and {chess.square_name(s2)}'
    )

    x_delta = int(math.copysign(1, x_delta))
    y_delta = int(math.copysign(1, y_delta))

    return y_delta * 8 + x_delta


def extend_ray(
    from_sq: chess.Square,
    towards_sq: chess.Square,
) -> chess.Bitboard:
    """
    Get a `chess.Bitboard` of all the squares from (and including) `from_sq`
    toward `towards_sq` and continuing on to an edge of the board.

    >>> print(chess.SquareSet(extend_ray(chess.C3, chess.F6)))
    . . . . . . . 1
    . . . . . . 1 .
    . . . . . 1 . .
    . . . . 1 . . .
    . . . 1 . . . .
    . . 1 . . . . .
    . . . . . . . .
    . . . . . . . .
    """
    d = _sliding_delta(from_sq, towards_sq)
    # noinspection PyProtectedMember
    return chess._sliding_attacks(from_sq, 0, [d]) | chess.BB_SQUARES[from_sq]
