from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database.database import SessionLocal
from app.models.compra import Compra
from app.models.productos import Producto
from app.models.usuario import Usuario


router = APIRouter(prefix="/admin", tags=["Administrador"])
templates = Jinja2Templates(directory="app/views")


def _requiere_admin(request: Request) -> RedirectResponse | None:
    if not request.session.get("usuario_id"):
        return RedirectResponse(url="/", status_code=303)

    if request.session.get("rol") != "admin":
        return RedirectResponse(url="/usuario", status_code=303)

    return None


@router.get("")
def panel_admin(request: Request):
    respuesta = _requiere_admin(request)

    if respuesta:
        return respuesta

    db: Session = SessionLocal()

    try:
        usuarios = db.query(Usuario).order_by(Usuario.id.desc()).all()
        productos = (
            db.query(Producto)
            .options(joinedload(Producto.vendedor), joinedload(Producto.categoria))
            .order_by(Producto.id.desc())
            .all()
        )
        compras = (
            db.query(Compra)
            .options(
                joinedload(Compra.comprador),
                joinedload(Compra.producto).joinedload(Producto.vendedor),
            )
            .order_by(Compra.creada_en.desc())
            .all()
        )
    finally:
        db.close()

    return templates.TemplateResponse(
        request=request,
        name="admin/inicio.html",
        context={
            "request": request,
            "usuarios": usuarios,
            "productos": productos,
            "compras": compras,
            "nombre": request.session.get("nombre", "Administrador"),
        },
    )


@router.get("/inicio")
def panel_admin_alias(request: Request):
    return panel_admin(request)


@router.get("/usuarios")
def listar_usuarios(request: Request):
    respuesta = _requiere_admin(request)

    if respuesta:
        return respuesta

    db: Session = SessionLocal()

    try:
        usuarios = db.query(Usuario).all()
        return [
            {
                "id": u.id,
                "nombre": u.nombre,
                "email": u.email,
                "rol": u.rol,
                "activo": u.activo,
            }
            for u in usuarios
        ]
    finally:
        db.close()
