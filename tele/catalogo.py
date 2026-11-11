"""Catálogo de Tele-Dimensional: elementos cotidianos (con su dibujo), conceptos filosóficos, formatos de tele,
conflictos y voces. El sorteo evita repetir lo usado en los últimos episodios."""
import json
import os
import random
import re
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
HISTORIAL = os.path.join(AQUI, 'historial.json')

# id: (nombre con artículo, código del dibujo, True si el dibujo ya trae cara)
ELEMENTOS = {
    # comida
    'limon': ('un limón', '1f34b', 0), 'platano': ('un plátano', '1f34c', 0), 'pan': ('una barra de pan', '1f956', 0),
    'cruasan': ('un cruasán', '1f950', 0), 'queso': ('una cuña de queso', '1f9c0', 0), 'huevo': ('un huevo', '1f95a', 0),
    'pizza': ('una porción de pizza', '1f355', 0), 'hamburguesa': ('una hamburguesa', '1f354', 0),
    'patatas': ('unas patatas fritas', '1f35f', 0), 'taco': ('un taco', '1f32e', 0), 'donut': ('un dónut', '1f369', 0),
    'galleta': ('una galleta', '1f36a', 0), 'helado': ('un helado', '1f366', 0), 'tarta': ('un trozo de tarta', '1f370', 0),
    'aguacate': ('un aguacate', '1f951', 0), 'brocoli': ('un brócoli', '1f966', 0), 'zanahoria': ('una zanahoria', '1f955', 0),
    'tomate': ('un tomate', '1f345', 0), 'cebolla': ('una cebolla', '1f9c5', 0), 'ajo': ('una cabeza de ajo', '1f9c4', 0),
    'guindilla': ('una guindilla', '1f336', 0), 'mazorca': ('una mazorca', '1f33d', 0), 'sandia': ('una sandía', '1f349', 0),
    'pina': ('una piña', '1f34d', 0), 'cerezas': ('unas cerezas', '1f352', 0), 'fresa': ('una fresa', '1f353', 0),
    'coco': ('un coco', '1f965', 0), 'cafe': ('un café', '2615', 0), 'leche': ('un vaso de leche', '1f95b', 0),
    'cerveza': ('una caña de cerveza', '1f37a', 0), 'salero': ('un salero', '1f9c2', 0), 'lata': ('una lata de conserva', '1f96b', 0),
    'palomitas': ('unas palomitas', '1f37f', 0), 'paella': ('una paella', '1f958', 0), 'aceituna': ('una aceituna', '1fad2', 0),
    'patata': ('una patata', '1f954', 0), 'berenjena': ('una berenjena', '1f346', 0), 'pera': ('una pera', '1f350', 0),
    'manzana': ('una manzana', '1f34e', 0), 'miel': ('un tarro de miel', '1f36f', 0), 'bocadillo': ('un bocadillo', '1f96a', 0),
    'chocolate': ('una tableta de chocolate', '1f36b', 0), 'piruleta': ('una piruleta', '1f36d', 0),
    # casa y objetos
    'paraguas': ('un paraguas', '2602', 0), 'calcetin': ('un calcetín desparejado', '1f9e6', 0),
    'zapatilla': ('una zapatilla', '1f45f', 0), 'chistera': ('un sombrero de copa', '1f3a9', 0), 'gafas': ('unas gafas', '1f453', 0),
    'corbata': ('una corbata', '1f454', 0), 'mochila': ('una mochila', '1f392', 0), 'llave': ('una llave', '1f511', 0),
    'candado': ('un candado', '1f512', 0), 'bombilla': ('una bombilla', '1f4a1', 0), 'vela': ('una vela', '1f56f', 0),
    'linterna': ('una linterna', '1f526', 0), 'pila': ('una pila', '1f50b', 0), 'movil': ('un móvil', '1f4f1', 0),
    'portatil': ('un portátil', '1f4bb', 0), 'tele': ('una tele vieja', '1f4fa', 0), 'radio': ('una radio', '1f4fb', 0),
    'mando': ('un mando de consola', '1f3ae', 0), 'telefono': ('un teléfono fijo', '260e', 0),
    'despertador': ('un despertador', '23f0', 0), 'reloj_arena': ('un reloj de arena', '231b', 0),
    'libro': ('un libro', '1f4d6', 0), 'lapiz': ('un lápiz', '270f', 0), 'tijeras': ('unas tijeras', '2702', 0),
    'clip': ('un clip', '1f4ce', 0), 'chincheta': ('una chincheta', '1f4cc', 0), 'sobre': ('una carta', '2709', 0),
    'buzon': ('un buzón', '1f4ee', 0), 'periodico': ('un periódico', '1f4f0', 0), 'papelera': ('una papelera', '1f5d1', 0),
    'papel_higienico': ('un rollo de papel higiénico', '1f9fb', 0), 'jabon': ('una pastilla de jabón', '1f9fc', 0),
    'esponja': ('una esponja', '1f9fd', 0), 'cepillo': ('un cepillo de dientes', '1faa5', 0), 'escoba': ('una escoba', '1f9f9', 0),
    'cubo': ('un cubo', '1faa3', 0), 'vater': ('un váter', '1f6bd', 0), 'banera': ('una bañera', '1f6c1', 0),
    'sofa': ('un sofá', '1f6cb', 0), 'silla': ('una silla', '1fa91', 0), 'puerta': ('una puerta', '1f6aa', 0),
    'espejo': ('un espejo', '1fa9e', 0), 'escalera': ('una escalera de mano', '1fa9c', 0), 'maleta': ('una maleta', '1f9f3', 0),
    'globo': ('un globo', '1f388', 0), 'regalo': ('un regalo', '1f381', 0), 'dado': ('un dado', '1f3b2', 0),
    'balon': ('un balón', '26bd', 0), 'guitarra': ('una guitarra', '1f3b8', 0), 'trompeta': ('una trompeta', '1f3ba', 0),
    'tambor': ('un tambor', '1f941', 0), 'microfono': ('un micrófono', '1f3a4', 0), 'auriculares': ('unos auriculares', '1f3a7', 0),
    'camara': ('una cámara de fotos', '1f4f7', 0), 'bicicleta': ('una bicicleta', '1f6b2', 0), 'patinete': ('un patinete', '1f6f4', 0),
    'coche': ('un coche', '1f697', 0), 'autobus': ('un autobús', '1f68c', 0), 'semaforo': ('un semáforo', '1f6a6', 0),
    'ancla': ('un ancla', '2693', 0), 'cohete': ('un cohete', '1f680', 0), 'ovni': ('un platillo volante', '1f6f8', 0),
    'iman': ('un imán', '1f9f2', 0), 'martillo': ('un martillo', '1f528', 0), 'llave_inglesa': ('una llave inglesa', '1f527', 0),
    'tornillo': ('un tornillo', '1f529', 0), 'engranaje': ('un engranaje', '2699', 0), 'extintor': ('un extintor', '1f9ef', 0),
    'carrito': ('un carrito del súper', '1f6d2', 0), 'moneda': ('una moneda', '1fa99', 0), 'billete': ('un billete', '1f4b5', 0),
    'tarjeta': ('una tarjeta de crédito', '1f4b3', 0), 'tique': ('un tique de compra', '1f9fe', 0), 'corona': ('una corona', '1f451', 0),
    'anillo': ('un anillo', '1f48d', 0), 'diamante': ('un diamante', '1f48e', 0), 'osito': ('un osito de peluche', '1f9f8', 1),
    'yoyo': ('un yoyó', '1fa80', 0), 'cometa': ('una cometa', '1fa81', 0), 'bola_cristal': ('una bola de cristal', '1f52e', 0),
    'termometro': ('un termómetro', '1f321', 0), 'tirita': ('una tirita', '1fa79', 0), 'pastilla': ('una pastilla', '1f48a', 0),
    'microscopio': ('un microscopio', '1f52c', 0), 'telescopio': ('un telescopio', '1f52d', 0), 'antena': ('una antena parabólica', '1f4e1', 0),
    'desatascador': ('un desatascador', '1faa0', 0), 'ratonera': ('una ratonera', '1faa4', 0), 'cesta': ('una cesta', '1f9fa', 0),
    'ovillo': ('un ovillo de lana', '1f9f6', 0), 'imperdible': ('un imperdible', '1f9f7', 0), 'pincel': ('un pincel', '1f58c', 0),
    'trofeo': ('un trofeo', '1f3c6', 0), 'bolo': ('unos bolos', '1f3b3', 0), 'cactus': ('un cactus', '1f335', 0),
    'maceta': ('una planta de interior', '1fab4', 0), 'seta': ('una seta', '1f344', 0), 'girasol': ('un girasol', '1f33b', 0),
    'piedra': ('una piedra', '1faa8', 0), 'tronco': ('un tronco', '1fab5', 0), 'nube': ('una nube', '2601', 0),
    'rayo': ('un rayo', '26a1', 0), 'copo': ('un copo de nieve', '2744', 0), 'fuego': ('una llama', '1f525', 0),
    'gota': ('una gota de agua', '1f4a7', 0), 'luna': ('la luna', '1f319', 0), 'estrella': ('una estrella', '2b50', 0),
    'volcan': ('un volcán', '1f30b', 0), 'tetera': ('una tetera', '1fad6', 0), 'olla': ('una olla', '1f372', 0),
    'cuchara': ('una cuchara', '1f944', 0), 'botella': ('una botella', '1f37e', 0), 'bolsa': ('una bolsa de la compra', '1f6cd', 0),
    'caja': ('una caja de cartón', '1f4e6', 0), 'disquete': ('un disquete', '1f4be', 0), 'cinta': ('una cinta de vídeo', '1f4fc', 0),
    'megafono': ('un megáfono', '1f4e2', 0), 'campana': ('una campana', '1f514', 0), 'brujula': ('una brújula', '1f9ed', 0),
    'balanza': ('una balanza', '2696', 0), 'hucha': ('una hucha', '1f416', 1),
    # animales (ya traen cara)
    'paloma': ('una paloma', '1f54a', 1), 'pato': ('un pato', '1f986', 1), 'gallina': ('una gallina', '1f414', 1),
    'gato': ('un gato', '1f408', 1), 'perro': ('un perro', '1f415', 1), 'vaca': ('una vaca', '1f404', 1),
    'oveja': ('una oveja', '1f411', 1), 'caracol': ('un caracol', '1f40c', 1), 'hormiga': ('una hormiga', '1f41c', 1),
    'abeja': ('una abeja', '1f41d', 1), 'mosca': ('una mosca', '1fab0', 1), 'pulpo': ('un pulpo', '1f419', 1),
    'pez': ('un pez', '1f41f', 1), 'tortuga': ('una tortuga', '1f422', 1), 'rana': ('una rana', '1f438', 1),
    'buho': ('un búho', '1f989', 1), 'murcielago': ('un murciélago', '1f987', 1), 'cangrejo': ('un cangrejo', '1f980', 1),
    'flamenco': ('un flamenco', '1f9a9', 1), 'loro': ('un loro', '1f99c', 1), 'erizo': ('un erizo', '1f994', 1),
    'cabra': ('una cabra', '1f410', 1), 'raton': ('un ratón', '1f401', 1), 'lagarto': ('un lagarto', '1f98e', 1),
    'ballena': ('una ballena', '1f40b', 1), 'pinguino': ('un pingüino', '1f427', 1), 'nutria': ('una nutria', '1f9a6', 1),
    'gamba': ('una gamba', '1f990', 1), 'mariquita': ('una mariquita', '1f41e', 1), 'camello': ('un camello', '1f42a', 1),
    # conceptos cotidianos
    'wifi': ('la cobertura del wifi', '1f4f6', 0), 'siesta': ('la siesta', '1f4a4', 0), 'bateria_baja': ('la batería baja', '1faab', 0),
    'lunes': ('un lunes', '1f5d3', 0), 'contrasena': ('una contraseña olvidada', '1f510', 0), 'hipoteca': ('una hipoteca', '1f3e0', 0),
    'notificacion': ('una notificación', '1f4ac', 0), 'rebajas': ('las rebajas', '1f3f7', 0), 'sirena': ('una alarma', '1f6a8', 0),
    'ascensor': ('un ascensor', '1f6d7', 0), 'reciclaje': ('el reciclaje', '267b', 0), 'atasco': ('un atasco', '1f6a7', 0),
    'cumple': ('un cumpleaños', '1f382', 0), 'mudanza': ('una mudanza', '1f69a', 0), 'factura': ('una factura', '1f4c4', 0),
}

# decorado: dibujos que solo se usan para vestir los platós
ATREZO = {'mundo': '1f30d', 'sol': '2600', 'sarten': '1f373', 'planeta': '1fa90', 'ojo': '1f441', 'foco': '1f526',
          'etiqueta': '1f3f7', 'bola': '1f52e', 'vela_d': '1f56f', 'marcador': '1f3c1', 'bandera': '1f6a9'}

# (nombre, explicación de una línea para el guionista)
CONCEPTOS = [
    ('el barco de Teseo', 'si a algo le cambias todas sus piezas una a una, ¿sigue siendo lo mismo?'),
    ('la paradoja del abuelo', 'si viajas al pasado e impides tu propio nacimiento, ¿quién viajó?'),
    ('Aquiles y la tortuga (Zenón)', 'para llegar a la meta antes hay que recorrer la mitad, y antes la mitad de la mitad: nunca se llega'),
    ('la paradoja del mentiroso', '«esta frase es falsa»: si es verdad es mentira, y si es mentira es verdad'),
    ('la paradoja del montón (sorites)', 'un grano no es un montón; ¿en qué grano exacto empieza a serlo?'),
    ('el gato de Schrödinger', 'mientras nadie mira dentro de la caja, las dos posibilidades son ciertas a la vez'),
    ('el mito de Sísifo', 'empujar la piedra hasta arriba sabiendo que volverá a caer, y aun así seguir'),
    ('la caverna de Platón', 'confundir las sombras de la pared con la realidad, y enfadarse con quien sale a mirar'),
    ('la navaja de Ockham', 'la explicación más sencilla suele ser la correcta'),
    ('el asno de Buridán', 'entre dos opciones idénticas, quien no sabe elegir se muere de hambre'),
    ('el dilema del tranvía', '¿actuar para sacrificar a uno o no hacer nada y dejar que caigan cinco?'),
    ('el dilema del prisionero', 'si los dos cooperan ganan, pero a cada uno le tienta traicionar'),
    ('la habitación china', 'seguir las reglas a la perfección sin entender nada de lo que se dice'),
    ('el cerebro en una cubeta', 'no puedes demostrar que lo que vives no es una señal enchufada a tu cabeza'),
    ('la paradoja de Fermi', 'si el universo está lleno de vida, ¿dónde está todo el mundo?'),
    ('el eterno retorno', 'vivir esta misma vida, idéntica, infinitas veces: ¿la elegirías igual?'),
    ('el vuelo de Ícaro', 'quien ignora el aviso y vuela demasiado cerca del sol se derrite'),
    ('la caja de Pandora', 'abrir lo que no se debía y que dentro, al final, solo quede la esperanza'),
    ('Narciso', 'enamorarse del propio reflejo hasta no poder apartarse de él'),
    ('Prometeo', 'robar el fuego para regalarlo y pagar el castigo eternamente'),
    ('el rey Midas', 'pedir que todo lo que toques sea oro y descubrir que no puedes comer'),
    ('el suplicio de Tántalo', 'tener lo que deseas siempre a un palmo y no alcanzarlo nunca'),
    ('la espada de Damocles', 'el poder se disfruta con una espada colgando de un pelo sobre la cabeza'),
    ('el anillo de Giges', 'si fueras invisible y nadie pudiera pillarte, ¿seguirías siendo justo?'),
    ('el velo de la ignorancia', 'diseñar las reglas sin saber qué papel te tocará después'),
    ('el hotel infinito de Hilbert', 'un hotel con infinitas habitaciones llenas donde siempre cabe uno más'),
    ('el demonio de Laplace', 'si alguien conociera cada átomo, el futuro estaría ya escrito'),
    ('la paradoja de la tolerancia', 'tolerarlo todo, también al intolerante, acaba con la tolerancia'),
    ('la paradoja de la elección', 'cuantas más opciones tienes, peor eliges y menos disfrutas'),
    ('el examen sorpresa', 'si te avisan de que habrá sorpresa, se puede demostrar que no puede haberla… y aun así sorprende'),
    ('la paradoja de Newcomb', 'alguien que predice tu elección ya ha decidido el premio antes de que elijas'),
    ('la apuesta de Pascal', 'apostar por creer «por si acaso», porque perder cuesta poco y ganar es infinito'),
    ('la máquina de experiencias', '¿te enchufarías para siempre a una máquina que te hace sentir feliz?'),
    ('el zombi filosófico', 'alguien que actúa igual que tú pero no siente nada por dentro: ¿cómo lo distingues?'),
    ('el genio maligno de Descartes', 'quizá alguien te engaña en todo; lo único seguro es que dudas'),
    ('la tragedia de los comunes', 'lo que es de todos lo agota cada uno pensando que por uno no pasa nada'),
    ('el efecto Dunning-Kruger', 'quien menos sabe es quien más seguro está de saber'),
    ('la ley de Goodhart', 'cuando una medida se convierte en objetivo, deja de medir nada'),
    ('la paradoja de Abilene', 'un grupo hace lo que nadie quería porque cada uno creyó que los demás sí'),
    ('el problema de Monty Hall', 'cambiar de puerta duplica tus opciones aunque la intuición grite que da igual'),
    ('el uróboros', 'la serpiente que se muerde la cola: el final es el principio'),
    ('el nudo gordiano', 'el problema imposible de desatar se resuelve cortándolo'),
    ('el lecho de Procusto', 'estirar o recortar a la gente para que encaje en la cama, en vez de cambiar la cama'),
    ('la torre de Babel', 'un proyecto enorme que fracasa cuando nadie entiende a nadie'),
    ('Ulises y las sirenas', 'atarse al mástil hoy para no hacer caso mañana a la tentación'),
    ('el laberinto del Minotauro', 'entrar es fácil; salir exige un hilo que alguien te dio antes'),
    ('Orfeo y Eurídice', 'lo tenías todo ganado con una sola condición: no mirar atrás'),
    ('la tela de Penélope', 'deshacer de noche lo que haces de día para que nunca se acabe'),
    ('Casandra', 'saber exactamente lo que va a pasar y que nadie te crea'),
    ('Pigmalión', 'enamorarse de la propia obra hasta que cobra vida'),
    ('el pacto de Fausto', 'conseguirlo todo ahora a cambio de algo que parecía no importar'),
    ('el Gólem', 'la criatura creada para obedecer que cumple las órdenes demasiado al pie de la letra'),
    ('el efecto mariposa', 'un cambio diminuto al principio provoca un desastre enorme al final'),
    ('la paradoja de los gemelos', 'el que viaja rápido vuelve más joven que el que se quedó'),
    ('el argumento de la simulación', 'si se pueden simular mundos, lo más probable es que vivamos en uno'),
    ('el teorema del mono infinito', 'un mono tecleando al azar eternamente acabaría escribiendo el Quijote'),
    ('la paradoja del barbero', 'el barbero afeita a todos los que no se afeitan a sí mismos: ¿quién lo afeita a él?'),
    ('la paradoja de la piedra', '¿puede un ser todopoderoso crear una piedra que no pueda levantar?'),
    ('el dilema del erizo', 'cuanto más se acercan para darse calor, más se pinchan'),
    ('la paradoja del agua y los diamantes', 'lo imprescindible es barato y lo inútil, carísimo'),
    ('el principio de Peter', 'todo el mundo asciende hasta llegar al puesto en el que es incompetente'),
    ('la ley de Murphy', 'si algo puede salir mal, saldrá mal, y en el peor momento'),
    ('la paradoja de Jevons', 'cuanto más eficiente es algo, más se gasta'),
    ('el teletransportador de Parfit', 'si te copian en otro sitio y destruyen el original, ¿el que llega eres tú?'),
    ('el universo creado el jueves pasado', 'no puedes demostrar que el mundo no empezó hace cinco minutos con los recuerdos puestos'),
    ('la tetera de Russell', 'quien afirma algo indemostrable es quien debe probarlo, no los demás refutarlo'),
    ('la navaja de Hanlon', 'no atribuyas a la maldad lo que se explica por torpeza'),
    ('la paradoja del bootstrap', 'un objeto traído del futuro que nadie fabricó nunca: existe porque existe'),
    ('la biblioteca infinita', 'una biblioteca con todos los libros posibles donde es imposible encontrar el que dice la verdad'),
    ('el efecto Rashomon', 'cada testigo cuenta una versión distinta y todas son sinceras'),
    ('la paradoja de Epiménides', 'un cretense dice que todos los cretenses mienten'),
    ('el experimento del malvavisco', 'aguantar sin comerte uno ahora para tener dos después'),
    ('la falacia del coste hundido', 'seguir con algo malo solo por todo lo que ya has invertido'),
    ('la profecía autocumplida', 'creer que algo va a pasar es justo lo que hace que pase'),
    ('el cisne negro', 'lo que nadie creía posible ocurre, y después todos dicen que se veía venir'),
    ('la paradoja de Moravec', 'lo difícil para una persona es fácil para una máquina, y al revés'),
    ('el cuarto de Mary', 'saberlo todo sobre el color rojo no es lo mismo que verlo por primera vez'),
    ('el ser y la nada', 'estás condenado a elegir: incluso no elegir es una elección'),
    ('la paradoja del hedonismo', 'quien persigue la felicidad directamente es quien menos la alcanza'),
    ('memento mori', 'recordar que todo se acaba es lo que da valor a lo que hay'),
]

# id: (género, nombre de plató para el guionista, sonidos que le pegan)
FORMATOS = {
    'juicio': ('un juicio televisado', 'sala de vistas con estrado', ['mazo', 'murmullo']),
    'concurso': ('un concurso de preguntas', 'plató con ruleta y luces', ['ding', 'error', 'redoble', 'aplausos']),
    'informativo': ('un informativo de última hora', 'mesa de informativos con pantallas', ['alarma', 'ding']),
    'documental': ('un documental de naturaleza', 'paisaje alienígena al aire libre', ['whoosh', 'latido']),
    'reality': ('un reality de convivencia', 'confesionario con cortina y sofá', ['redoble', 'latido', 'aplausos']),
    'debate': ('un debate político a dos', 'plató partido en dos colores con atriles', ['error', 'murmullo', 'ding']),
    'cocina': ('un programa de cocina', 'cocina de plató con estantes', ['ding', 'whoosh', 'caja']),
    'teletienda': ('una teletienda de madrugada', 'pedestal con destellos', ['caja', 'ding', 'aplausos']),
    'tiempo': ('el parte meteorológico', 'mapa del tiempo gigante', ['whoosh', 'alarma']),
    'late': ('un programa de entrevistas nocturno', 'cortinón, mesa y ciudad de fondo', ['redoble', 'aplausos', 'ding']),
    'consultorio': ('un consultorio de videncia con llamadas', 'gabinete con bola de cristal y velas', ['latido', 'ding', 'laser']),
    'deportes': ('una retransmisión deportiva', 'estadio con marcador', ['aplausos', 'redoble', 'error']),
}

CONFLICTOS = [
    'alguien ha desaparecido en directo y nadie quiere admitirlo', 'el premio no existe y solo uno lo sabe',
    'hay un impostor en el plató', 'el programa no puede terminar hasta que alguien diga la verdad',
    'el presentador quiere dimitir en directo', 'el público ha votado algo imposible de cumplir',
    'el patrocinador exige un cambio absurdo a mitad de emisión', 'una avería mezcla este universo con el de al lado',
    'hay que elegir a quién salvar antes de la publicidad', 'nadie recuerda las reglas y todos fingen que sí',
    'el invitado estrella es la persona menos indicada', 'la prueba decisiva se ha comido a sí misma',
    'dos versiones del mismo personaje reclaman ser la original', 'el tiempo del programa corre hacia atrás',
    'alguien ha leído el guion y sabe cómo acaba', 'la audiencia es una sola persona y está a punto de cambiar de canal',
    'un objeto del plató exige derechos laborales', 'lo que se anuncia ya lo ha comprado todo el mundo, incluso antes de existir',
    'el experto invitado no ha existido nunca', 'cada respuesta correcta empeora las cosas',
    'el ganador será castigado y el perdedor, premiado', 'una noticia se cumple solo si se emite',
    'alguien intenta escapar del programa por la pantalla', 'el regidor ha perdido el control del decorado',
    'un error de emisión ha convertido el ensayo en el programa real', 'los papeles se han intercambiado sin que nadie lo pidiera',
    'el jurado tiene que juzgarse a sí mismo', 'falta un ingrediente que nadie sabe nombrar',
]

# PUERTAS ABIERTAS (vacías = no se usan). Ver tele/COMO-EDITAR.md
# Universos o contextos donde puede pasar el episodio: «una dimensión donde el tiempo va hacia atrás», …
CONTEXTOS = []
# Personajes que pueden repetir: {'nombre': 'Nutria Roja', 'cuerpo': 'nutria', 'voz': 'presentadora',
#                                  'personalidad': 'presentadora del canal, sarcástica'}
PERSONAJES_FIJOS = []
PROB_FIJO = 0.5          # probabilidad de que salga uno de los personajes fijos en un episodio

# preset: (voz de edge-tts, velocidad, tono, descripción para la ficha)
VOCES = {
    'locutor': ('es-ES-AlvaroNeural', '+14%', '-6Hz', 'locutor de continuidad, grave y solemne'),
    'presentador_canal': ('es-ES-AlvaroNeural', '+4%', '-10Hz', 'voz del canal, grave y épica'),
    'grave': ('es-MX-JorgeNeural', '+6%', '-22Hz', 'voz grave y lenta, de autoridad cansada'),
    'aguda': ('es-ES-ElviraNeural', '+16%', '+28Hz', 'voz aguda y acelerada, nerviosa'),
    'presentadora': ('es-ES-XimenaNeural', '+12%', '+4Hz', 'presentadora de tele, sonrisa de plástico'),
    'chillon': ('es-AR-TomasNeural', '+20%', '+38Hz', 'voz chillona y repelente'),
    'cavernosa': ('es-US-AlonsoNeural', '+2%', '-34Hz', 'voz cavernosa, de criatura enorme'),
    'dulce': ('es-CO-SalomeNeural', '+8%', '+14Hz', 'voz dulce que inquieta un poco'),
    'castizo': ('es-ES-AlvaroNeural', '+18%', '+12Hz', 'voz de tertuliano castizo que habla rápido'),
    'robot': ('es-CL-LorenzoNeural', '+10%', '-12Hz', 'voz plana y funcionarial'),
    'anciana': ('es-CU-BelkysNeural', '-2%', '-10Hz', 'voz de señora mayor que lo ha visto todo'),
}


def historial():
    try:
        return json.load(open(HISTORIAL))
    except (OSError, ValueError):
        return []


def sorteo(semilla=None):
    """Saca al azar 3 elementos, un concepto, un formato y un conflicto, sin repetir lo reciente."""
    rng = random.Random(semilla) if semilla is not None else random.SystemRandom()
    h = historial()
    el_rec = {e for x in h[-12:] for e in x.get('elementos', [])}
    co_rec = {x.get('concepto') for x in h[-60:]}
    fo_rec = [x.get('formato') for x in h[-4:]]
    cf_rec = {x.get('conflicto') for x in h[-15:]}
    ids = [k for k in ELEMENTOS if k not in el_rec]
    # como mucho un animal y un concepto por episodio, para que haya variedad de siluetas
    for _ in range(200):
        tres = rng.sample(ids, 3)
        if sum(ELEMENTOS[k][2] for k in tres) <= 1:
            break
    conceptos = [c for c in CONCEPTOS if c[0] not in co_rec] or CONCEPTOS
    formatos = [f for f in FORMATOS if f not in fo_rec] or list(FORMATOS)
    conflictos = [c for c in CONFLICTOS if c not in cf_rec] or CONFLICTOS
    c = rng.choice(conceptos)
    extra = {}
    if CONTEXTOS:
        extra['contexto'] = rng.choice(CONTEXTOS)
    if PERSONAJES_FIJOS and rng.random() < PROB_FIJO:
        extra['fijo'] = rng.choice(PERSONAJES_FIJOS)
    return {**extra, 'elementos': tres, 'concepto': c[0], 'concepto_idea': c[1], 'formato': rng.choice(formatos),
            'conflicto': rng.choice(conflictos), 'paleta': rng.randrange(8), 'dimension': f"{rng.choice('BDFGHJKLMNPQRTVXZ')}-{rng.randrange(100, 9999)}",
            'semilla': rng.randrange(1 << 30)}


def _norma(t):
    t = ''.join(c for c in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9ñ]+', '_', t).strip('_')


_ARTICULOS = re.compile(r'^(un|una|unos|unas|el|la|los|las)_')


def buscar(palabra):
    """Id del catálogo que corresponde a una palabra libre («Paraguas», «un limón»), o None."""
    n = _norma(palabra)
    if n in ELEMENTOS:
        return n
    n2 = _ARTICULOS.sub('', n)
    for k, v in ELEMENTOS.items():
        nombre = _ARTICULOS.sub('', _norma(v[0]))
        if n2 in (k, nombre) or (len(n2) > 3 and nombre.startswith(n2)):
            return k
    return None


def libre(palabra):
    """Id para cualquier palabra: la del catálogo si existe, si no la palabra limpia (se dibuja como criatura)."""
    return buscar(palabra) or _norma(palabra)[:24] or 'cosa'


def nombre(e):
    """Cómo se dice un elemento: «un limón» si está en el catálogo, la palabra tal cual si es libre."""
    return ELEMENTOS[e][0] if e in ELEMENTOS else e.replace('_', ' ')


def desde_idea(idea, semilla=None):
    """Un sorteo construido a partir de una idea del banco (ChatGPT o Claude). Lo que la idea no trae, no se fuerza."""
    rng = random.Random(semilla) if semilla is not None else random.SystemRandom()
    base = sorteo(semilla)
    campos = ('titulo', 'premisa', 'chiste', 'giro', 'gancho', 'protagonista', 'desarrollo', 'audiovisual', 'genero', 'formato_texto')
    s = dict(base, elementos=[libre(e) for e in idea.get('elementos') or []][:3], concepto=idea.get('concepto') or '',
             concepto_idea=idea.get('premisa', ''), formato=idea.get('formato') if idea.get('formato') in FORMATOS else base['formato'],
             conflicto=idea.get('conflicto') or idea.get('desarrollo') or base['conflicto'],
             idea={k: idea.get(k, '') for k in campos}, idea_clave=idea.get('clave'), idea_fuente=idea.get('fuente'),
             paleta=rng.randrange(8))
    if idea.get('universo'):
        s['contexto'] = idea['universo']
    return s
