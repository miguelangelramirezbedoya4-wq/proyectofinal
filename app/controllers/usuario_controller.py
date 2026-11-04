import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.categoria import Categoria
from app.models.carrito import Carrito
from app.models.compra import Compra
from app.models.mensaje import Mensaje
from app.models.intercambio import SolicitudIntercambio
from app.models.productos import Producto


router = APIRouter(
    prefix="/usuario",
    tags=["Usuario"]
)

templates = Jinja2Templates(directory="app/views")
logger = logging.getLogger(__name__)


def _usuario_autenticado(request: Request) -> bool:
    return bool(request.session.get("usuario_id"))


def _redirigir_si_no_hay_sesion(request: Request) -> RedirectResponse | None:
    if not _usuario_autenticado(request):
        return RedirectResponse(url="/", status_code=303)

    return None


def _contexto_usuario(request: Request, **extra):
    contexto = {
        "request": request,
        "nombre": request.session.get("nombre", "Usuario"),
    }
    contexto.update(extra)
    return contexto


def _filtrar_productos_para_compra(producto: Producto, usuario_id: int | None) -> bool:
    if usuario_id is None:
        return True
    if producto is None:
        return False
    if producto.vendedor_id is None:
        return True
    return producto.vendedor_id != usuario_id


@router.get("")
def inicio_usuario(request: Request):
    respuesta = _redirigir_si_no_hay_sesion(request)

    if respuesta:
        return respuesta

    return templates.TemplateResponse(
        request=request,
        name="usuario/inicio.html",
        context=_contexto_usuario(request),
    )


@router.get("/inicio")
def inicio_usuario_alias(request: Request):
    return inicio_usuario(request)


@router.get("/objetos")
def listar_objetos(
    request: Request,
    mis_publicaciones: bool = False,
    db: Session = Depends(get_db),
):
    respuesta = _redirigir_si_no_hay_sesion(request)

    if respuesta:
        return respuesta

    usuario_id = request.session.get("usuario_id")
    query = db.query(Producto)
    if mis_publicaciones:
        query = query.filter(Producto.vendedor_id == usuario_id)
    else:
        query = query.filter(Producto.disponible.is_(True))
        query = query.filter(or_(Producto.vendedor_id.is_(None), Producto.vendedor_id != usuario_id))

    return templates.TemplateResponse(
        request=request,
        name="usuario/objetos.html",
        context=_contexto_usuario(
            request,
            objetos=query.order_by(Producto.id.desc()).all(),
            vista_propia=mis_publicaciones,
            resultado=request.query_params.get("resultado"),
        ),
    )


@router.post("/objetos/{producto_id}/eliminar")
def eliminar_objeto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta

    producto = db.get(Producto, producto_id)
    usuario_id = request.session["usuario_id"]
    if not producto or producto.vendedor_id != usuario_id:
        raise HTTPException(status_code=404, detail="No se encontró el objeto publicado por tu cuenta.")

    if db.query(Compra).filter(Compra.producto_id == producto.id).first():
        return RedirectResponse(
            url="/usuario/objetos?mis_publicaciones=true&resultado=vendido",
            status_code=303,
        )

    tiene_propuestas = db.query(SolicitudIntercambio).filter(
        or_(
            SolicitudIntercambio.producto_solicitado_id == producto.id,
            SolicitudIntercambio.producto_ofrecido_id == producto.id,
        )
    ).first()
    tiene_mensajes = db.query(Mensaje).filter(Mensaje.producto_id == producto.id).first()
    if tiene_propuestas or tiene_mensajes:
        return RedirectResponse(
            url="/usuario/objetos?mis_publicaciones=true&resultado=historial",
            status_code=303,
        )

    nombre_imagen = producto.imagen
    imagen_compartida = (
        db.query(Producto)
        .filter(Producto.imagen == nombre_imagen, Producto.id != producto.id)
        .first()
        if nombre_imagen
        else None
    )
    db.query(Carrito).filter(Carrito.producto_id == producto.id).delete()
    db.delete(producto)
    db.commit()

    if nombre_imagen and not imagen_compartida and Path(nombre_imagen).name == nombre_imagen:
        ruta_imagen = Path(__file__).resolve().parents[1] / "static" / "uploads" / nombre_imagen
        try:
            ruta_imagen.unlink(missing_ok=True)
        except OSError:
            logger.exception("No se pudo borrar el archivo de imagen del producto %s", producto_id)

    return RedirectResponse(
        url="/usuario/objetos?mis_publicaciones=true&resultado=eliminado",
        status_code=303,
    )


@router.get("/publicar")
def mostrar_publicar(request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)

    if respuesta:
        return respuesta

    return templates.TemplateResponse(
        request=request,
        name="usuario/publicar.html",
        context=_contexto_usuario(request, categorias=db.query(Categoria).order_by(Categoria.nombre).all()),
    )


@router.post("/publicar")
async def publicar_objeto(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio: int | None = Form(None),
    modalidad: str = Form("venta"),
    categorias_intercambio: list[str] | None = Form(None),
    intercambio_por: str = Form(""),
    categoria_id: int = Form(...),
    imagen: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    respuesta = _redirigir_si_no_hay_sesion(request)

    if respuesta:
        return respuesta

    nombre = nombre.strip()
    descripcion = descripcion.strip()

    if not nombre or not descripcion:
        return templates.TemplateResponse(
            request=request,
            name="usuario/publicar.html",
            context=_contexto_usuario(
                request,
                error="Debes completar el nombre y la descripcion del objeto.",
                categorias=db.query(Categoria).order_by(Categoria.nombre).all(),
            ),
            status_code=400,
        )

    categoria = db.get(Categoria, categoria_id)
    es_intercambio = modalidad == "intercambio"
    if modalidad not in {"venta", "intercambio"} or not categoria or (not es_intercambio and (precio is None or precio < 0)):
        return templates.TemplateResponse(
            request=request, name="usuario/publicar.html",
            context=_contexto_usuario(request, error="Selecciona una categoría y un precio válido para la venta.", categorias=db.query(Categoria).all()),
            status_code=400,
        )

    preferencias_intercambio = None
    if es_intercambio:
        opciones_validas = {
            "Escolar", "Oficina", "Libros", "Tecnología", "Arte y manualidades",
            "Hogar", "Acepto propuestas variadas",
        }
        preferencias = [
            opcion for opcion in (categorias_intercambio or [])
            if opcion in opciones_validas
        ]
        detalle_intercambio = intercambio_por.strip()[:500]
        if detalle_intercambio:
            preferencias.append(detalle_intercambio)
        preferencias_intercambio = ", ".join(dict.fromkeys(preferencias)) or "Acepto propuestas variadas"

    nombre_archivo = None
    if imagen and imagen.filename:
        extension = Path(imagen.filename).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            return templates.TemplateResponse(
                request=request, name="usuario/publicar.html",
                context=_contexto_usuario(request, error="La imagen debe ser JPG, PNG o WEBP.", categorias=db.query(Categoria).all()),
                status_code=400,
            )
        carpeta = Path("app/static/uploads")
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre_archivo = f"{uuid4().hex}{extension}"
        (carpeta / nombre_archivo).write_bytes(await imagen.read())

    producto = Producto(
        nombre=nombre, descripcion=descripcion, precio=0 if es_intercambio else precio,
        es_intercambio=es_intercambio, intercambio_por=preferencias_intercambio,
        categoria_id=categoria.id,
        vendedor_id=request.session["usuario_id"], imagen=nombre_archivo, disponible=True,
    )
    db.add(producto)
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="usuario/publicar.html",
        context=_contexto_usuario(
            request,
            mensaje=(
                f"Objeto '{nombre}' publicado correctamente."
            ),
            categorias=db.query(Categoria).order_by(Categoria.nombre).all(),
        ),
    )


@router.get("/objetos/{producto_id}")
def detalle_objeto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Objeto no encontrado.")
    return templates.TemplateResponse(request=request, name="usuario/detalle_objeto.html", context=_contexto_usuario(request, objeto=producto))


@router.get("/intercambio/{producto_id}")
def mostrar_propuesta_intercambio(producto_id: int, request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    producto = db.get(Producto, producto_id)
    if not producto or not producto.disponible or not producto.es_intercambio:
        raise HTTPException(status_code=404, detail="Este objeto no está disponible para intercambio.")
    if producto.vendedor_id == request.session["usuario_id"]:
        raise HTTPException(status_code=400, detail="No puedes proponer un intercambio por tu propio objeto.")
    objetos_propios = db.query(Producto).filter(
        Producto.vendedor_id == request.session["usuario_id"], Producto.disponible.is_(True)
    ).order_by(Producto.nombre).all()
    return templates.TemplateResponse(request=request, name="usuario/proponer_intercambio.html", context=_contexto_usuario(
        request, objeto=producto, objetos_propios=objetos_propios
    ))


@router.post("/intercambio/{producto_id}")
def crear_propuesta_intercambio(
    producto_id: int, request: Request, producto_ofrecido_id: int = Form(...), mensaje: str = Form(""), db: Session = Depends(get_db)
):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    solicitante_id = request.session["usuario_id"]
    solicitado = db.get(Producto, producto_id)
    ofrecido = db.get(Producto, producto_ofrecido_id)
    if not solicitado or not solicitado.disponible or not solicitado.es_intercambio:
        raise HTTPException(status_code=404, detail="El objeto solicitado ya no está disponible para intercambio.")
    if not ofrecido or not ofrecido.disponible or ofrecido.vendedor_id != solicitante_id or ofrecido.id == solicitado.id:
        raise HTTPException(status_code=400, detail="Selecciona uno de tus objetos disponibles para ofrecer.")
    repetida = db.query(SolicitudIntercambio).filter(
        SolicitudIntercambio.solicitante_id == solicitante_id,
        SolicitudIntercambio.producto_solicitado_id == solicitado.id,
        SolicitudIntercambio.producto_ofrecido_id == ofrecido.id,
        SolicitudIntercambio.estado == "pendiente",
    ).first()
    if not repetida:
        solicitud = SolicitudIntercambio(
            solicitante_id=solicitante_id, producto_solicitado_id=solicitado.id,
            producto_ofrecido_id=ofrecido.id, mensaje=mensaje.strip() or None,
        )
        db.add(solicitud)
        db.flush()
        contenido = f"Te propusieron intercambiar {ofrecido.nombre} por {solicitado.nombre}."
        if solicitud.mensaje:
            contenido += f" Mensaje: {solicitud.mensaje}"
        db.add(Mensaje(
            remitente_id=solicitante_id,
            destinatario_id=solicitado.vendedor_id,
            producto_id=solicitado.id,
            solicitud_intercambio_id=solicitud.id,
            contenido=contenido,
        ))
        db.commit()
    return RedirectResponse(url="/usuario/intercambios", status_code=303)


@router.get("/intercambios")
def listar_intercambios(request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    usuario_id = request.session["usuario_id"]
    solicitudes = db.query(SolicitudIntercambio).join(
        Producto, SolicitudIntercambio.producto_solicitado_id == Producto.id
    ).filter(
        (SolicitudIntercambio.solicitante_id == usuario_id) | (Producto.vendedor_id == usuario_id)
    ).order_by(SolicitudIntercambio.creada_en.desc()).all()
    return templates.TemplateResponse(request=request, name="usuario/intercambios.html", context=_contexto_usuario(
        request, solicitudes=solicitudes, usuario_id=usuario_id
    ))


@router.post("/intercambios/{solicitud_id}/{accion}")
def responder_intercambio(solicitud_id: int, accion: str, request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    solicitud = db.get(SolicitudIntercambio, solicitud_id)
    if not solicitud or solicitud.producto_solicitado.vendedor_id != request.session["usuario_id"]:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if solicitud.estado != "pendiente" or accion not in {"aceptar", "rechazar"}:
        raise HTTPException(status_code=400, detail="Esta solicitud ya fue gestionada.")
    if accion == "aceptar":
        if (
            not solicitud.producto_solicitado.disponible
            or not solicitud.producto_ofrecido.disponible
            or solicitud.producto_ofrecido.vendedor_id != solicitud.solicitante_id
        ):
            raise HTTPException(status_code=400, detail="Uno de los objetos ya no está disponible.")
        solicitud.producto_solicitado.disponible = False
        solicitud.producto_ofrecido.disponible = False
        solicitud.estado = "aceptada"
        for otra in db.query(SolicitudIntercambio).filter(SolicitudIntercambio.estado == "pendiente").all():
            usa_objeto_intercambiado = (
                otra.producto_solicitado_id in {solicitud.producto_solicitado_id, solicitud.producto_ofrecido_id}
                or otra.producto_ofrecido_id in {solicitud.producto_solicitado_id, solicitud.producto_ofrecido_id}
            )
            if otra.id != solicitud.id and usa_objeto_intercambiado:
                otra.estado = "rechazada"
    else:
        solicitud.estado = "rechazada"
    db.commit()
    return RedirectResponse(url="/usuario/intercambios", status_code=303)


@router.get("/mensaje/{producto_id}")
def mostrar_mensaje(producto_id: int, request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Objeto no encontrado.")
    return templates.TemplateResponse(request=request, name="usuario/enviar_mensaje.html", context=_contexto_usuario(request, objeto=producto))


@router.post("/mensaje/{producto_id}")
def enviar_mensaje(producto_id: int, request: Request, contenido: str = Form(...), db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)
    if respuesta:
        return respuesta
    producto = db.get(Producto, producto_id)
    if not producto or not producto.vendedor_id:
        raise HTTPException(status_code=404, detail="Objeto no encontrado.")
    if producto.vendedor_id == request.session["usuario_id"]:
        raise HTTPException(status_code=400, detail="No puedes enviarte mensajes a ti mismo.")
    contenido = contenido.strip()
    if not contenido:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    db.add(Mensaje(remitente_id=request.session["usuario_id"], destinatario_id=producto.vendedor_id, producto_id=producto.id, contenido=contenido))
    db.commit()
    return RedirectResponse(url="/usuario/mensajes", status_code=303)


@router.get("/mensajes")
def listar_mensajes(request: Request, db: Session = Depends(get_db)):
    respuesta = _redirigir_si_no_hay_sesion(request)

    if respuesta:
        return respuesta

    return templates.TemplateResponse(
        request=request,
        name="usuario/mensajes.html",
        context=_contexto_usuario(
            request,
            mensajes=db.query(Mensaje).filter(
                (Mensaje.remitente_id == request.session["usuario_id"]) |
                (Mensaje.destinatario_id == request.session["usuario_id"])
            ).order_by(Mensaje.creado_en.desc()).all(),
            usuario_id=request.session["usuario_id"],
        ),
    )
