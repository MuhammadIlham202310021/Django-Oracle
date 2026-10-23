
<?php
// Menghasilkan simbol ≥
echo "Lebih besar atau sama dengan: ≥ <br>";

// Menghasilkan simbol >=
echo "Lebih besar atau sama dengan: >= <br>";

// Menggunakan HTML Entity
echo "Menggunakan HTML Entity: &ge;";
?>

<?php
$operator = '>=';

// Mengubah operator menjadi simbol untuk tampilan report
if ($operator === '>=') {
    echo '&ge;';
} else {
    echo htmlspecialchars($operator);
}
?>