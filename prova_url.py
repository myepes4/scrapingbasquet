import requests
import pandas as pd
import time
import random

# Demanar la URL a l'usuari
url_base = input("Introdueix la URL del partit: ")

# Demanar el nom del partit
nom_partit = input("Introdueix el nom del partit: ")

# Generem un timestamp únic amb un número aleatori per evitar la memòria cau
timestamp = int(time.time()) + random.randint(1, 1000)

# Afegir el timestamp a la URL
url = f"{url_base}&_={timestamp}"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()  # Dades del partit

    jugades = []
    jugadores_titulars_local = set()  # Jugadores titulars de l'equip local
    jugadores_titulars_visitant = set()  # Jugadores titulars de l'equip visitant
    jugadores_que_han_entrat = set()  # Jugadores que han entrat al camp
    temps_jugadores = {}  # Diccionari per emmagatzemar els minuts jugats

    # Identificar els dos equips a partir de les primeres jugades
    equips = set()
    for jugada in data:
        equip = jugada.get("idTeam")
        if equip != 0:  # Ignorem el valor 0
            equips.add(equip)
        if len(equips) == 2:  # Ja hem trobat els dos equips
            break

    if len(equips) != 2:
        print("❌ Error: No s'han pogut identificar els dos equips correctament.")
        exit()

    equip_1, equip_2 = equips  # Els dos equips identificats

    # Determinar quin equip és local i quin és visitant
    equip_local = None
    equip_visitant = None

    for jugada in data:
        equip = jugada.get("idTeam")
        marcador = jugada.get("score", "0-0")
        marcador_local, marcador_visitant = map(int, marcador.split("-"))

        if equip == equip_1 and marcador_local > 0:
            equip_local = equip_1
            equip_visitant = equip_2
            break
        elif equip == equip_2 and marcador_local > 0:
            equip_local = equip_2
            equip_visitant = equip_1
            break

    if not equip_local or not equip_visitant:
        print("❌ Error: No s'ha pogut determinar quin equip és local i quin és visitant.")
        exit()

    print(f"✅ Equip local identificat: {equip_local}")
    print(f"✅ Equip visitant identificat: {equip_visitant}")

    # Processar jugades
    for jugada in data:
        equip = jugada.get("idTeam", "Desconegut")
        jugadora = jugada.get("actorName", "Desconegut")
        accio = jugada.get("move", "Desconeguda")
        minut = jugada.get("min", 0)
        segon = jugada.get("sec", 0)
        periode = jugada.get("period", 1)
        marcador = jugada.get("score", "0-0")
        marcador_local, marcador_visitant = map(int, marcador.split("-"))

        # Convertir temps a segons des de l'inici del partit
        temps = (10 - minut) * 60 - segon + (periode - 1) * 600

        # Registrar jugada
        jugades.append({
            "Equip": equip,
            "Jugadora": jugadora,
            "Acció": accio,
            "Minut": f"{minut}:{segon:02d}",
            "Període": periode,
            "Marcador Local": marcador_local,
            "Marcador Visitant": marcador_visitant,
            "Temps": temps  # Afegim el temps en segons per facilitar els càlculs
        })

        # Detectar jugadores titulars
        if "Entra al camp" in accio:
            jugadores_que_han_entrat.add(jugadora)
        elif "Surt del camp" in accio and jugadora not in jugadores_que_han_entrat:
            # Si surt sense haver entrat, és titular
            if str(equip) == str(equip_local):  # Comparem com a cadenes per evitar problemes de format
                jugadores_titulars_local.add(jugadora)
            else:
                jugadores_titulars_visitant.add(jugadora)
        elif ("Cistella" in accio or "Falta" in accio or "Salt guanyat" in accio) and jugadora not in jugadores_que_han_entrat:
            # Si fa una acció sense haver entrat, és titular
            if str(equip) == str(equip_local):
                jugadores_titulars_local.add(jugadora)
            else:
                jugadores_titulars_visitant.add(jugadora)

    # Afegir minuts per a les titulars (comencen a jugar des del minut 0)
    for jugadora in jugadores_titulars_local.union(jugadores_titulars_visitant):
        if jugadora not in temps_jugadores:
            temps_jugadores[jugadora] = {"Entrades": [0], "Sortides": [], "Minuts Acumulats": 0}

    # Gestionar entrades/sortides per calcular minuts jugats
    for jugada in data:
        jugadora = jugada.get("actorName", "Desconegut")
        accio = jugada.get("move", "Desconeguda")
        minut = jugada.get("min", 0)
        segon = jugada.get("sec", 0)
        periode = jugada.get("period", 1)

        # Convertir temps a segons des de l'inici del partit
        temps = (10 - minut) * 60 - segon + (periode - 1) * 600

        if "Entra al camp" in accio:
            if jugadora not in temps_jugadores:
                temps_jugadores[jugadora] = {"Entrades": [], "Sortides": [], "Minuts Acumulats": 0}
            temps_jugadores[jugadora]["Entrades"].append(temps)
        elif "Surt del camp" in accio:
            if jugadora in temps_jugadores:
                temps_jugadores[jugadora]["Sortides"].append(temps)
                # Calcular minuts jugats en aquest interval
                entrada = temps_jugadores[jugadora]["Entrades"][-1]
                sortida = temps
                minuts_jugats = (sortida - entrada) / 60
                temps_jugadores[jugadora]["Minuts Acumulats"] += minuts_jugats

    # Calcular minuts per a jugadores que no surten després de la seva última entrada
    for jugadora, temps in temps_jugadores.items():
        entrades = temps["Entrades"]
        sortides = temps["Sortides"]
        if len(entrades) > len(sortides):
            entrada = entrades[-1]
            sortida = 2400  # Final del partit
            minuts_jugats = (sortida - entrada) / 60
            temps_jugadores[jugadora]["Minuts Acumulats"] += minuts_jugats

    # Funció per calcular punts fets i rebuts basant-se en el marcador
    def calcular_punts_marcador(jugades, temps_inici, temps_fi, equip_jugadora):
        marcador_inici = {"local": 0, "visitant": 0}
        marcador_fi = {"local": 0, "visitant": 0}

        # Trobar el marcador quan la jugadora entra
        for jugada in jugades:
            if jugada["Temps"] >= temps_inici:
                marcador_inici["local"] = jugada["Marcador Local"]
                marcador_inici["visitant"] = jugada["Marcador Visitant"]
                break

        # Trobar el marcador quan la jugadora surt
        for jugada in reversed(jugades):
            if jugada["Temps"] <= temps_fi:
                marcador_fi["local"] = jugada["Marcador Local"]
                marcador_fi["visitant"] = jugada["Marcador Visitant"]
                break

        # Calcular punts fets i rebuts segons l'equip de la jugadora
        if str(equip_jugadora) == str(equip_local):  # Comparem com a cadenes per evitar problemes de format
            punts_fets = marcador_fi["local"] - marcador_inici["local"]
            punts_rebuts = marcador_fi["visitant"] - marcador_inici["visitant"]
        else:  # Equip visitant
            punts_fets = marcador_fi["visitant"] - marcador_inici["visitant"]
            punts_rebuts = marcador_fi["local"] - marcador_inici["local"]

        return punts_fets, punts_rebuts

    # Funció per mostrar el resum per a un equip específic
    def mostrar_resum_equip(jugades, temps_jugadores, equip_id, nom_equip):
        resum = []  # Llista per emmagatzemar les dades del resum
        print(f"\nResum per jugadora ({nom_equip}):")
        print("{:<25} {:<15} {:<15} {:<15} {:<15}".format(
            "Jugadora", "Minuts jugats", "Punts fets", "Punts rebuts", "Plus/Minus"
        ))
        for jugadora, temps in temps_jugadores.items():
            # Identificar l'equip de la jugadora
            equip_jugadora = None
            for jugada in data:
                if jugada.get("actorName") == jugadora:
                    equip_jugadora = jugada.get("idTeam")
                    break

            # Verificar si la jugadora pertany a l'equip especificat
            if str(equip_jugadora) == str(equip_id):  # Comparem com a cadenes per evitar problemes de format
                entrades = temps["Entrades"]
                sortides = temps["Sortides"]

                # Si no surt al final del partit, assumeix que ha jugat fins al final
                if len(entrades) > len(sortides):
                    sortides.append(2400)  # Final del partit

                # Variables per acumular els punts fets i rebuts
                punts_fets_totals = 0
                punts_rebuts_totals = 0

                # Calcular punts fets i rebuts per a cada franja de temps
                for i in range(len(entrades)):
                    temps_inici = entrades[i]
                    temps_fi = sortides[i] if i < len(sortides) else 2400

                    punts_fets, punts_rebuts = calcular_punts_marcador(jugades, temps_inici, temps_fi, equip_jugadora)
                    punts_fets_totals += punts_fets
                    punts_rebuts_totals += punts_rebuts

                # Calcular Plus/Minus
                plus_minus = punts_fets_totals - punts_rebuts_totals

                # Afegir les dades al resum
                resum.append({
                    "Jugadora": jugadora,
                    "Minuts jugats": temps["Minuts Acumulats"],
                    "Punts fets": punts_fets_totals,
                    "Punts rebuts": punts_rebuts_totals,
                    "Plus/Minus": plus_minus
                })

                # Mostrar resultats per consola
                print("{:<25} {:<15.2f} {:<15} {:<15} {:<15}".format(
                    jugadora, temps["Minuts Acumulats"], punts_fets_totals, punts_rebuts_totals, plus_minus
                ))

        return resum

    # Mostrar resum per a l'equip local i visitant
    resum_local = mostrar_resum_equip(jugades, temps_jugadores, equip_local, "Local")
    resum_visitant = mostrar_resum_equip(jugades, temps_jugadores, equip_visitant, "Visitant")

    # Crear un DataFrame amb les dades del resum
    df_resum = pd.DataFrame(resum_local + resum_visitant)

    # Exportar a Excel amb el nom del partit
    nom_fitxer = f"plusminus_{nom_partit}.xlsx"
    df_resum.to_excel(nom_fitxer, index=False)
    print(f"\n✅ Dades desades correctament a '{nom_fitxer}'")

else:
    print(f"❌ Error en la petició: {response.status_code}")