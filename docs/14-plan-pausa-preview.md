# Plan — pausa al inicio y al final de «Probar clip»

**Fecha:** 2026-10-16

**Estado:** plan para revisar. El código de reproducción no se ha cambiado.

## Qué se oye

Al pulsar **Probar clip**, el tramo seleccionado arranca con una pausa y, al llegar al final, vuelve a haber una pausa antes de repetirse. Los `.webm` y `.mp3` generados de las mismas líneas no tienen ese silencio ni al inicio ni al final.

Ejemplo revisado: `data/output_files/Ratatouille_S01E01_Line_0001.webm` (y las líneas 0002 y 0003). Esos archivos están bien cortados. La pausa solo existe en la previsualización.

## A qué se debe

«Probar clip» no reproduce el archivo ya cortado. Reproduce el MKV entero y le pide a mpv que salte al segundo de inicio y que, al llegar al final, salte otra vez al inicio.

Eso está en `_enable_segment_loop()`:

```2797:2805:gui_app.py
def _enable_segment_loop(self, start: float, end: float):
    self.player.command("seek", start, "absolute")
    self.player.ab_loop_a = start
    self.player.ab_loop_b = end
    self.player.pause = False
    self._segment_loop_active = True
    self._start_playback_timer()
    self._update_play_button()
    self._update_position_label()
```

Un BDRip H.264 no puede saltar a un segundo cualquiera al instante. El fotograma clave anterior puede estar varios segundos atrás. Para empezar exactamente en `start`, mpv tiene que decodificar desde ese fotograma clave hasta el instante pedido. Mientras lo hace, la imagen se queda quieta y el audio no suena. Esa es la pausa del inicio.

Al llegar a `ab-loop-b`, mpv hace el mismo salto de vuelta a `ab-loop-a`. Otra decodificación, otra pausa, y solo entonces el bucle vuelve a sonar. Por eso se nota justo al terminar el tramo y al empezar la repetición.

El `.webm` y el `.mp3` ya salen recortados. Su primer fotograma es el inicio del clip, así que el reproductor no tiene que buscar en medio del MKV. ffmpeg hace ese recorte en el momento de generar (`cut_single_clip`: salto grueso y después `trim`/`atrim` exactos). El padding por defecto es `0`, así que la previsualización y el archivo cubren el mismo intervalo; la diferencia es el salto, no un trozo de silencio añadido al archivo.

La lista de la interfaz y el temporizador de posición se actualizan una vez al pulsar el botón. No se vuelven a ejecutar en cada vuelta del bucle. La demora repetida está dentro de libmpv, al decodificar el salto.

Un reinicio de audio WASAPI puede sumar unas decenas de milisegundos después de cada salto. En un MKV largo, lo que se nota es la decodificación hasta el instante exacto.

## Qué no conviene hacer

Dejar el salto en el fotograma clave más cercano (`hr-seek=no`) arranca al momento, pero suena el diálogo de antes del clip. Sirve mal para comprobar el corte.

## Cambio propuesto

Cuando se pulse **Probar clip**, reproducir un archivo corto que ya empiece en el inicio del tramo, en bucle (`loop-file`), en lugar del MKV completo con A–B.

1. Si ya existe el `.webm` de esa línea y los tiempos coinciden con los de la pantalla, reproducir ese `.webm` en bucle. Es el mismo archivo que se revisa fuera del programa.
2. Si todavía no existe, generar un previo temporal con un codificador rápido (por ejemplo x264 `ultrafast`), no con VP9. VP9 es el códec del archivo final y es lento para una escucha de unos segundos.
3. Mostrar en la barra de estado que se está preparando la escucha, y al terminar reproducir el temporal en bucle.
4. Si cambian Start o End, el temporal deja de valer. La siguiente pulsación de **Probar clip** genera otro. Mientras no se pulse de nuevo, no hace falta recodificar en cada movimiento del spinbox.
5. **Generar clip** sigue creando el `.webm` VP9 y el `.mp3` como ahora. El temporal no sustituye a esos archivos.

Así la primera escucha de una línea espera un encode corto, y las repeticiones del bucle arrancan como el archivo exportado: sin salto dentro del MKV.

## Cómo comprobarlo después de implementarlo

1. Abrir el MKV de Ratatouille, cargar el `.srt` y pulsar **Probar clip** en una línea de unos pocos segundos.
2. La primera vez puede haber una espera corta mientras se prepara el previo. Al sonar, el inicio debe entrar directo en la frase.
3. Dejar que el bucle dé al menos dos vueltas. Entre el final y el nuevo inicio no debe haber una pausa larga.
4. Generar el clip y comparar el `.webm` y el `.mp3` con esa escucha: el contenido debe seguir siendo el mismo tramo, sin silencio añadido.
5. Cambiar Start o End y volver a pulsar **Probar clip**: la escucha debe seguir los tiempos nuevos.
