"""Tradução das classes do modelo para linguagem do produtor.

As orientações são de manejo cultural geral. Não indicam produto nem dose: isso exige
receituário agronômico. Revise este conteúdo com um agrônomo antes de usar em campo.
"""

SAUDAVEL = "saudavel"
DOENCA = "doenca"

_MANTER = "Nenhum sinal de doença encontrado nesta folha. Continue olhando a lavoura toda semana."
_SEM_MOLHAR = "Evite molhar as folhas ao irrigar e não mexa nas plantas quando estiverem molhadas."

CLASSES = {
    "Tomato leaf": ("Tomate", "Folha sadia", SAUDAVEL, _MANTER),
    "Tomato Early blight leaf": (
        "Tomate", "Pinta-preta", DOENCA,
        "Retire as folhas de baixo atingidas, leve-as para longe da lavoura e faça rotação de culturas.",
    ),
    "Tomato Septoria leaf spot": (
        "Tomate", "Septoriose", DOENCA,
        f"Retire as folhas com manchas e mantenha as plantas arejadas. {_SEM_MOLHAR}",
    ),
    "Tomato leaf bacterial spot": (
        "Tomate", "Mancha-bacteriana", DOENCA,
        f"{_SEM_MOLHAR} Limpe as ferramentas e use mudas e sementes sadias.",
    ),
    "Tomato leaf late blight": (
        "Tomate", "Requeima", DOENCA,
        "A requeima avança rápido em tempo frio e úmido. Procure assistência técnica o quanto antes e separe as plantas atingidas.",
    ),
    "Tomato leaf mosaic virus": (
        "Tomate", "Mosaico (vírus)", DOENCA,
        "O vírus passa pelas mãos e ferramentas. Arranque as plantas atingidas e lave as mãos e ferramentas antes de tocar nas outras.",
    ),
    "Tomato leaf yellow virus": (
        "Tomate", "Enrolamento-amarelo (vírus da mosca-branca)", DOENCA,
        "Procure mosca-branca embaixo das folhas, arranque as plantas muito atingidas e peça orientação sobre o controle do inseto.",
    ),
    "Tomato mold leaf": (
        "Tomate", "Mofo-das-folhas", DOENCA,
        "Abra espaço entre as plantas para o ar circular, principalmente em estufa, e retire as folhas atingidas.",
    ),
    "Corn Gray leaf spot": (
        "Milho", "Cercosporiose", DOENCA,
        "Faça rotação de culturas e, no próximo plantio, escolha híbridos mais resistentes.",
    ),
    "Corn leaf blight": (
        "Milho", "Helmintosporiose", DOENCA,
        "Acompanhe se as manchas sobem para as folhas de cima, faça rotação de culturas e escolha híbridos mais resistentes.",
    ),
    "Corn rust leaf": (
        "Milho", "Ferrugem", DOENCA,
        "Veja quantas plantas têm os pontinhos de ferrugem e procure assistência técnica se estiverem se espalhando.",
    ),
    "Potato leaf early blight": (
        "Batata", "Pinta-preta", DOENCA,
        "Retire as folhas atingidas e faça rotação de culturas. Mantenha as plantas bem nutridas.",
    ),
    "Potato leaf late blight": (
        "Batata", "Requeima", DOENCA,
        "A requeima avança rápido em tempo frio e úmido. Procure assistência técnica o quanto antes e separe as plantas atingidas.",
    ),
    "Bell_pepper leaf": ("Pimentão", "Folha sadia", SAUDAVEL, _MANTER),
    "Bell_pepper leaf spot": (
        "Pimentão", "Mancha-bacteriana", DOENCA,
        f"{_SEM_MOLHAR} Limpe as ferramentas e use mudas e sementes sadias.",
    ),
    "Squash Powdery mildew leaf": (
        "Abóbora", "Oídio", DOENCA,
        "Retire as folhas com pó branco e abra espaço para o ar circular entre as plantas.",
    ),
    "Soyabean leaf": ("Soja", "Folha sadia", SAUDAVEL, _MANTER),
    "Strawberry leaf": ("Morango", "Folha sadia", SAUDAVEL, _MANTER),
    "grape leaf": ("Uva", "Folha sadia", SAUDAVEL, _MANTER),
    "grape leaf black rot": (
        "Uva", "Podridão-negra", DOENCA,
        "Retire e leve para longe as folhas e os frutos atingidos, inclusive os secos que ficaram na planta.",
    ),
}

AVISO = (
    "Este resultado é uma sugestão e pode estar errado. Confirme com um agrônomo ou com a "
    "assistência técnica (ATER) antes de tomar uma decisão. Produtos químicos só com "
    "receituário agronômico."
)

MENSAGENS = {
    "possivel_doenca": "Encontramos sinais de uma possível doença.",
    "folha_saudavel": "A folha parece saudável.",
    "inconclusivo": "Não temos certeza. Tire outra foto de perto, com boa luz e a folha em foco.",
    "nada_detectado": "Não encontramos uma folha conhecida. Hoje reconhecemos tomate, milho, batata, pimentão, abóbora, soja, morango e uva.",
}
