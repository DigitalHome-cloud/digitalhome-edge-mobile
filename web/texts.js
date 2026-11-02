// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 DigitalHome.cloud
// The phone's own words (app.js, actions.js), in English, French and German. A profile's words are in the profile.
'use strict';
var TEXTS = {
  en: { hint: 'Tap to start', insecure: 'Not a secure page: the camera is blocked. Use USB (localhost) or HTTPS.',
        nolink: 'No link to the edge', back: 'Back', cancel: 'Cancel', next: 'Next', ok: 'OK', send: 'Send', sent: 'Sent',
        skip: 'Skip', retake: 'Again', use: 'Use it', shoot: 'Take the photo', reading: 'Reading the text…',
        notext: 'No text found', textok: 'Is the text right? Change it if not.', scanning: 'Looking for a code…',
        typeit: 'Type the code', nocam: 'The camera does not open', step: 'Step', of: 'of', review: 'Is everything right?',
        empty: '—', waiting: 'waiting…', on: 'on', off: 'off', photo: 'photo', code: 'code' },
  fr: { hint: 'Touchez pour commencer', insecure: 'Page non sécurisée : la caméra est bloquée. Passez par USB (localhost) ou HTTPS.',
        nolink: 'Pas de lien avec l’edge', back: 'Retour', cancel: 'Annuler', next: 'Suivant', ok: 'OK', send: 'Envoyer', sent: 'Envoyé',
        skip: 'Passer', retake: 'Refaire', use: 'Garder', shoot: 'Prendre la photo', reading: 'Lecture du texte…',
        notext: 'Pas de texte trouvé', textok: 'Le texte est-il juste ? Sinon, corrigez-le.', scanning: 'Recherche d’un code…',
        typeit: 'Taper le code', nocam: 'La caméra ne s’ouvre pas', step: 'Étape', of: 'sur', review: 'Tout est juste ?',
        empty: '—', waiting: 'en attente…', on: 'allumé', off: 'éteint', photo: 'photo', code: 'code' },
  de: { hint: 'Zum Starten tippen', insecure: 'Keine sichere Seite: die Kamera ist gesperrt. USB (localhost) oder HTTPS nutzen.',
        nolink: 'Keine Verbindung zum Edge', back: 'Zurück', cancel: 'Abbrechen', next: 'Weiter', ok: 'OK', send: 'Senden', sent: 'Gesendet',
        skip: 'Überspringen', retake: 'Nochmal', use: 'Nehmen', shoot: 'Foto machen', reading: 'Text wird gelesen…',
        notext: 'Kein Text gefunden', textok: 'Stimmt der Text? Sonst korrigieren.', scanning: 'Suche nach einem Code…',
        typeit: 'Code eintippen', nocam: 'Die Kamera geht nicht auf', step: 'Schritt', of: 'von', review: 'Stimmt alles?',
        empty: '—', waiting: 'wartet…', on: 'an', off: 'aus', photo: 'Foto', code: 'Code' }
};
