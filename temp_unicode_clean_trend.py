# Trend PB BO Unicode Replacement Script

# Dosyayı oku
file_path = 'src/strategy/trend_pb_bo.py'
print(f'Processing {file_path}...')

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Unicode character replacements - comprehensive Turkish character mapping
    replacements = {
        # Dotless I variations
        'ı': 'i',  # LATIN SMALL LETTER DOTLESS I → LATIN SMALL LETTER I
        'İ': 'I',  # LATIN CAPITAL LETTER I WITH DOT ABOVE → LATIN CAPITAL LETTER I

        # Other Turkish characters
        'ş': 's',  # LATIN SMALL LETTER S WITH CEDILLA → LATIN SMALL LETTER S
        'Ş': 'S',  # LATIN CAPITAL LETTER S WITH CEDILLA → LATIN CAPITAL LETTER S
        'ğ': 'g',  # LATIN SMALL LETTER G WITH BREVE → LATIN SMALL LETTER G
        'Ğ': 'G',  # LATIN CAPITAL LETTER G WITH BREVE → LATIN CAPITAL LETTER G
        'ü': 'u',  # LATIN SMALL LETTER U WITH DIAERESIS → LATIN SMALL LETTER U
        'Ü': 'U',  # LATIN CAPITAL LETTER U WITH DIAERESIS → LATIN CAPITAL LETTER U
        'ö': 'o',  # LATIN SMALL LETTER O WITH DIAERESIS → LATIN SMALL LETTER O
        'Ö': 'O',  # LATIN CAPITAL LETTER O WITH DIAERESIS → LATIN CAPITAL LETTER O
        'ç': 'c',  # LATIN SMALL LETTER C WITH CEDILLA → LATIN SMALL LETTER C
        'Ç': 'C',  # LATIN CAPITAL LETTER C WITH CEDILLA → LATIN CAPITAL LETTER C

        # Special characters
        '–': '-',  # EN DASH → HYPHEN-MINUS
        '—': '-',  # EM DASH → HYPHEN-MINUS
        '×': 'x',  # MULTIPLICATION SIGN → LATIN SMALL LETTER X
    }

    # Apply replacements
    changes_made = 0
    for old_char, new_char in replacements.items():
        if old_char in content:
            old_count = content.count(old_char)
            content = content.replace(old_char, new_char)
            changes_made += old_count
            print(f'  Replaced {old_count} instances of "{old_char}" with "{new_char}"')

    if changes_made > 0:
        # Write the cleaned content back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'✅ Unicode characters replaced successfully! Total changes: {changes_made}')
    else:
        print('No Unicode characters found to replace.')

except Exception as e:
    print(f'Error processing file: {e}')
