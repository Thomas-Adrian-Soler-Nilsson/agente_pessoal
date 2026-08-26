// calculadora simples
function calcular(a, b, operacao) {
    a = Number(a);
    b = Number(b);
    switch (operacao) {
        case '+':
            return a + b;
        case '-':
            return a - b;
        case '*':
            return a * b;
        case '/':
            if (b === 0) {
                return 'Erro: divisão por zero';
            }
            return a / b;
        default:
            return 'Operação inválida';
    }
}

// Exemplo de uso (remova ou comente se não precisar)
// console.log(calcular(5, 3, '+'));
