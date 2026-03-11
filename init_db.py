from app import app, db, Usuario, Conta, Categoria

with app.app_context():
    db.create_all()
    user = Usuario.query.first()
    if not user:
        user = Usuario(nome="Usuário Padrão", tema="dark")
        db.session.add(user)
        db.session.commit()
    
    # Criar uma conta padrão se nâo existir
    if not Conta.query.first():
        conta = Conta(nome="Carteira", tipo="dinheiro", saldo_inicial=0.0, usuario_id=user.id)
        db.session.add(conta)
        db.session.commit()

    print("Banco de dados resetado com sucesso.")
