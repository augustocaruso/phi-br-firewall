from __future__ import annotations


def only_digits(value: str) -> str:
    return "".join(char for char in value if "0" <= char <= "9")


def validate_cpf(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    numbers = [int(digit) for digit in digits]
    first_sum = sum(numbers[index] * (10 - index) for index in range(9))
    first_digit = (first_sum * 10) % 11
    if first_digit == 10:
        first_digit = 0
    if first_digit != numbers[9]:
        return False

    second_sum = sum(numbers[index] * (11 - index) for index in range(10))
    second_digit = (second_sum * 10) % 11
    if second_digit == 10:
        second_digit = 0
    return second_digit == numbers[10]
