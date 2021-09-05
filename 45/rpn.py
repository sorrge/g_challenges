from fractions import Fraction
import math


def rational_factorial(x):
    if x.denominator != 1:
        raise RuntimeError(f"Trying to take factorial of a non-integer {x.numerator}/{x.denominator}")

    return Fraction(math.factorial(x.numerator))


def rational_power(x, y):
    if y.denominator != 1:
        raise RuntimeError(f"Non-integer power not supported: {y.numerator}/{y.denominator}")

    return x ** y.numerator



binary_ops = {
    "+": lambda x, y: x + y,
    "-": lambda x, y: x - y,
    "*": lambda x, y: x * y,
    "/": lambda x, y: x / y,
    "^": rational_power,
}

unary_ops = {
    "!": rational_factorial
}


def error_at(text, pos, message):
    msg_text = message + "\n" + text[:pos] + " HERE >>>" + text[pos:]
    raise RuntimeError(msg_text)


def parse(text: str):
    lexems = []
    current_lexem = ""
    lexem_start = 0
    for i, c in enumerate(text):
        if c.isspace():
            if current_lexem != "":
                lexems.append((current_lexem, lexem_start))
                current_lexem = ""
            
            continue

        if c in unary_ops or c in binary_ops:
            if current_lexem != "":
                lexems.append((current_lexem, lexem_start))
            
            lexems.append((c, i))
            current_lexem = ""
            continue

        if c == ".":
            if current_lexem != "" and not current_lexem.isdigit():
                raise error_at(text, i, "Unexpected decimal point:")
        elif not c.isdigit():
            raise error_at(text, i, "Unexpected character:")
            
        if current_lexem == "":
            lexem_start = i

        current_lexem += c

    if current_lexem != "":
        lexems.append((current_lexem, lexem_start))

    processed_lexems = []
    for lexem, start in lexems:
        if lexem.isdigit():
            processed_lexems.append((Fraction(lexem), start))
        elif set(lexem).issubset(set("01234567890.")):
            processed_lexems.append((Fraction(int(lexem.replace(".", "")), 10 ** len(lexem.split(".")[1])), start))
        else:
            processed_lexems.append((lexem, start))

    return processed_lexems


print(f"Welcome to the reverse Polish notation calculator. Supported operations: {''.join(binary_ops)}{''.join(unary_ops)}\n"
      "Integers and simple floating point numbers are supported.\n"
      "All calculations are exact.\nCtrl-C or Ctrl-D to exit.")

try:
    while True:
        text = input("> ")
        try:
            stack = []
            for lexem, start in parse(text):
                if lexem in binary_ops:
                    if len(stack) < 2:
                        error_at(text, start, "Not enough arguments for operation:")

                    arg2 = stack.pop()
                    arg1 = stack.pop()
                    try:
                        stack.append(binary_ops[lexem](arg1, arg2))
                    except RuntimeError as e:
                        error_at(text, start, str(e))
                elif lexem in unary_ops:
                    if len(stack) < 1:
                        error_at(text, start, "Not enough arguments for operation:")
                    
                    try:
                        stack.append(unary_ops[lexem](stack.pop()))
                    except RuntimeError as e:
                        error_at(text, start, str(e))                        
                else:
                    stack.append(lexem)

            for n in stack:
                if n.denominator == 1:
                    print(n.numerator)
                else:
                    print(f"{n.numerator}/{n.denominator}")

        except RuntimeError as e:
            print(f"Error: {e}")
        
except EOFError:
    print("Bye!")
except KeyboardInterrupt:
    print("Bye!")
