import re
from typing import TypeAlias

import chess

FenType: TypeAlias = str

CORNER_SQUARES = chess.SquareSet(chess.BB_CORNERS)
EDGE_SQUARES = chess.SquareSet(
    chess.BB_RANK_1 | chess.BB_RANK_8 | chess.BB_FILE_A | chess.BB_FILE_H
)


DIAGONAL_SLIDERS = {chess.BISHOP, chess.QUEEN}
ORTHOGONAL_SLIDERS = {chess.ROOK, chess.QUEEN}
SLIDERS = DIAGONAL_SLIDERS | ORTHOGONAL_SLIDERS


PROMOTION_PIECE_TYPES = [
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
]
PROMOTION_PIECE_SYMBOLS = [
    chess.piece_symbol(pt).upper() for pt in PROMOTION_PIECE_TYPES
]
PROMOTION_PIECE_NAMES = [chess.piece_name(pt) for pt in PROMOTION_PIECE_TYPES]


CAPTURABLE_PIECE_TYPES = [
    chess.PAWN,
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
]

PAWN_SAN_REGEX = re.compile(
    r'^(?:(?P<file_disambiguator>[a-h])(?P<capture>[\-x]))?(?P<to_square>[a-h][1-8])(?:=(?P<promotion>[NBRQ]))?(?P<check_or_mate>[+#])?\Z'
)

NON_PAWN_SAN_REGEX = re.compile(
    r'^'
    r'(?P<piece_type>[NBKRQ])'
    r'(?P<file_disambiguator>[a-h])?'
    r'(?P<rank_disambiguator>[1-8])?'
    r'(?P<capture>[\-x])?'
    r'(?P<to_square>[a-h][1-8])'
    r'(?P<check_or_mate>[+#])?'
    r'\Z'
)
