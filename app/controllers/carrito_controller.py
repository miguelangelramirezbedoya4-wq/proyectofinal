from secrets import token_hex

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.carrito import Carrito
from app.models.compra import Compra
from app.models.productos import Producto

router = APIRouter(prefix="/carrito", tags=["carrito"])
templates = Jinja2Templates(directory="app/views")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _cantidad_carrito(db: Session, usuario_id: int) -> int:
    items = db.query(Carrito).filter(Carrito.usuario_id == usuario_id).all()
    return sum(item.cantidad for item in items)

@router.get("/")
def ver_carrito(request: Request, db: Session = Depends(get_db)):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return RedirectResponse(url="/", status_code=303)
    items = db.query(Carrito).filter(Carrito.usuario_id == usuario_id).all()
    cantidad_carrito = _cantidad_carrito(db, usuario_id)
    return templates.TemplateResponse(
        request=request,
        name="usuario/carrito.html",
        context={
            "items": items,
            "cantidad_carrito": cantidad_carrito,
            "nombre": request.session.get("nombre", "Usuario"),
        },
    )


@router.get("/contador")
def obtener_contador_carrito(request: Request, db: Session = Depends(get_db)):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return {"cantidad": 0}
    return {"cantidad": _cantidad_carrito(db, usuario_id)}


@router.post("/agregar/{producto_id}")
def agregar_al_carrito(producto_id: int, request: Request, db: Session = Depends(get_db)):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para agregar productos.")
    producto = db.get(Producto, producto_id)
    if not producto or not producto.disponible:
        raise HTTPException(status_code=404, detail="Producto no disponible.")
    if producto.es_intercambio:
        raise HTTPException(status_code=400, detail="Este objeto se ofrece únicamente para intercambio. Contacta al publicador.")
    if producto.vendedor_id == usuario_id:
        raise HTTPException(status_code=400, detail="No puedes agregar tu propio producto.")
    if not producto.vendedor_id:
        raise HTTPException(status_code=400, detail="Este producto todavía no está habilitado para la compra.")
    item = db.query(Carrito).filter(Carrito.usuario_id == usuario_id, Carrito.producto_id == producto_id).first()
    if item:
        return {"ok": True, "mensaje": "El producto ya está en tu carrito.", "cantidad": _cantidad_carrito(db, usuario_id)}
    db.add(Carrito(usuario_id=usuario_id, producto_id=producto_id, cantidad=1))
    db.commit()
    return {"ok": True, "mensaje": "Producto agregado al carrito.", "cantidad": _cantidad_carrito(db, usuario_id)}


@router.post("/quitar/{producto_id}")
def quitar_del_carrito(producto_id: int, request: Request, db: Session = Depends(get_db)):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión.")
    eliminado = db.query(Carrito).filter(
        Carrito.usuario_id == usuario_id, Carrito.producto_id == producto_id
    ).delete()
    db.commit()
    if not eliminado:
        raise HTTPException(status_code=404, detail="Producto no encontrado en el carrito.")
    return {"ok": True, "mensaje": "Producto eliminado del carrito."}


@router.post("/comprar/{producto_id}")
def comprar_producto(
    producto_id: int,
    request: Request,
    db: Session = Depends(get_db),
    metodo_pago: str = "tarjeta_prueba",
):
    comprador_id = request.session.get("usuario_id")
    if not comprador_id:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para comprar.")
    item = db.query(Carrito).filter(
        Carrito.usuario_id == comprador_id, Carrito.producto_id == producto_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Agrega el producto al carrito antes de confirmar la compra.")
    metodos_pago = {
        "tarjeta_prueba": "Tarjeta de prueba",
        "transferencia_simulada": "Transferencia simulada",
    }
    if metodo_pago not in metodos_pago:
        raise HTTPException(status_code=400, detail="Selecciona un método de pago del simulador.")
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    if not producto.vendedor_id:
        raise HTTPException(status_code=400, detail="Este producto aún no tiene vendedor asignado.")
    if producto.vendedor_id == comprador_id:
        raise HTTPException(status_code=400, detail="No puedes comprar tu propio producto.")
    if producto.es_intercambio:
        raise HTTPException(status_code=400, detail="Este objeto se ofrece únicamente para intercambio.")
    if not producto.disponible:
        raise HTTPException(status_code=409, detail="Este producto ya no está disponible.")

    actualizado = db.query(Producto).filter(
        Producto.id == producto.id, Producto.disponible.is_(True)
    ).update({Producto.disponible: False}, synchronize_session=False)
    if not actualizado:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este producto acaba de ser vendido.")

    precio_unitario = producto.precio
    total = precio_unitario * item.cantidad
    referencia_pago = f"EI-{token_hex(4).upper()}"
    estado = "pago_simulado_aprobado"
    db.add(Compra(
        comprador_id=comprador_id,
        producto_id=producto.id,
        cantidad=item.cantidad,
        precio_unitario=precio_unitario,
        total=total,
        metodo_pago=metodo_pago,
        referencia_pago=referencia_pago,
        estado=estado,
    ))
    db.query(Carrito).filter(
        Carrito.usuario_id == comprador_id, Carrito.producto_id == producto.id
    ).delete()
    db.commit()
    return {
        "ok": True,
        "mensaje": "Pago simulado aprobado. El vendedor podrá contactarte por el WhatsApp de tu perfil.",
        "metodo_pago": metodos_pago[metodo_pago],
        "referencia_pago": referencia_pago,
        "compra": {
            "producto": producto.nombre,
            "cantidad": item.cantidad,
            "precio_unitario": precio_unitario,
            "total": total,
            "estado": estado,
        },
    }


@router.get("/ventas")
def ver_ventas(request: Request, db: Session = Depends(get_db)):
    vendedor_id = request.session.get("usuario_id")
    if not vendedor_id:
        return RedirectResponse(url="/", status_code=303)
    ventas = (db.query(Compra).join(Producto).filter(Producto.vendedor_id == vendedor_id)
              .order_by(Compra.creada_en.desc()).all())
    compras_realizadas = (db.query(Compra).filter(Compra.comprador_id == vendedor_id)
                         .order_by(Compra.creada_en.desc()).all())
    return templates.TemplateResponse(
        request=request,
        name="usuario/ventas.html",
        context={
            "ventas": ventas,
            "compras_realizadas": compras_realizadas,
            "nombre": request.session.get("nombre", "Usuario"),
        },
    )
