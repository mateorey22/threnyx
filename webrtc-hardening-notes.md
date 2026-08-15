# Notes de fiabilité WebRTC — Threnyx

Le correctif v21 retire les transceivers ajoutés en doublon après `addTrack`, rattache les pistes distantes au flux négocié fourni par l’événement `track`, et accepte une offre de redémarrage ICE venant du pair déjà en appel. Le redémarrage est déclenché lorsque l’état ICE devient `failed`, ou reste `disconnected` pendant 4,5 secondes.

Ces choix suivent le modèle de négociation qui évite les courses entre descriptions SDP, et l’usage de `restartIce()` avant une nouvelle offre. La validation complète reste à réaliser sur deux appareils et sur des réseaux distincts, en particulier pour les restrictions d’autoplay audio des navigateurs mobiles.

## Références

1. [MDN — Perfect negotiation](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Perfect_negotiation)
2. [MDN — RTCPeerConnection.restartIce()](https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/restartIce)
3. [MDN — RTCPeerConnection.addTransceiver()](https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/addTransceiver)
