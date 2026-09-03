# LAN Multiplayer

Pinecraft unterstützt lokale Mehrspielersitzungen über TCP und UDP im selben
Netzwerk. TCP transportiert verlässliche Welt- und Verbindungsdaten, UDP die
verlusttoleranten Bewegungsdaten.
Der Host ist für Welt, Physik und Remote-Spieler autoritativ. Netzwerk-Threads
transportieren ausschließlich Nachrichten; Änderungen an Spielobjekten passieren
im Arcade-Spielthread.

## Host starten

1. Im Hauptmenü **Host LAN World** wählen.
2. Eine Welt aus dem Ordner `saves/` auswählen und **Start LAN Server** wählen.
	Der Standardport ist `25565`.
3. Nach dem Start steht die LAN-Adresse oben links, zum Beispiel
	`LAN Host: 192.168.178.23:25565`.
4. Eingehende Verbindungen durch die Betriebssystem-Firewall erlauben.

## Beitreten

1. Im Hauptmenü **Join LAN World** wählen.
2. Einen Anzeigenamen, die IP-Adresse des Hosts und denselben Port eintragen.
3. **Join** wählen. Der Server übermittelt Seed, Weltname und den gespeicherten
	Weltzustand automatisch. Dadurch stimmen Terrain, Wasser und Lava beim
	Beitritt mit der Host-Welt überein.

Zum Testen auf demselben Computer ist `127.0.0.1` als Host-IP geeignet.

## Aktueller Umfang

- Verbinden, Trennen, Anzeigenamen und eindeutige Server-Spieler-IDs.
- Synchronisierte Lauf- und Sprungbewegung für Host und beigetretene Spieler.
- Zwanzigmal pro Sekunde vom Host gesendete Spielersnapshots mit Position,
  Bewegung, Blickrichtung und Animationszustand über UDP. Zu große Snapshots
  fallen automatisch auf TCP zurück.
- Join-Clients spielen die empfangenen Animationszustände mit ihrer lokalen
	Bildrate weiter.
- Join-Clients sagen ihre eigenen Eingaben lokal voraus und gleichen sich bei
	jedem vom Host bestätigten Input-Zähler wieder ab.
- Fremde Spielerpositionen werden zwischen Snapshots lokal interpoliert.
- Vom Host bestätigte Blockänderungen werden an Clients übertragen.

Interaktionen mit Blöcken, Inventar, Mobs und Flüssigkeiten sind für beigetretene
Clients bewusst noch gesperrt. So gibt es keine konkurrierenden Weltänderungen,
bis die jeweiligen Aktionen als Server-Kommandos implementiert sind.

## Technischer Aufbau

- `network/protocol.py`: TCP-Frames und begrenzte UDP-JSON-Datagramme.
- `network/server.py`: TCP-Listener, UDP-Socket und Client-Eingaben in einer Queue.
- `network/client.py`: TCP-/UDP-Eingangsnachrichten in einer Queue.
- `GameView`: verarbeitet Queues, simuliert Remote-Spieler auf dem Host und
  wendet Snapshots auf Clients an.
