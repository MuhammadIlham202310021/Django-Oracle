from datetime import datetime


# === Fungsi bantu tampilan ===
def _ke_input(value, tipe):
    """Ubah nilai dari Oracle menjadi teks untuk kolom isian."""
    if value is None:
        return ''
    if tipe == 'date':
        return value.strftime('%Y-%m-%d')
    if tipe == 'number':
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
    return str(value)

def _tampil(value):
    if isinstance(value, datetime):
        return value.strftime('%d-%m-%Y %H:%M')
    return '' if value is None else value
# === End Fungsi bantu tampilan ===