from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.categoria import Categoria
from app.models.productos import Producto

router = APIRouter(prefix="/categorias", tags=["categorias"])
templates = Jinja2Templates(directory="app/views")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def listar_categorias(request: Request, db: Session = Depends(get_db)):
    categorias = db.query(Categoria).order_by(Categoria.nombre).all()
    return templates.TemplateResponse(
        request,
        "usuario/categorias.html",
        {"categorias": categorias, "nombre": request.session.get("nombre", "Usuario")},
    )


@router.get("/{categoria_id}")
def productos_categoria(categoria_id: int, request: Request, db: Session = Depends(get_db)):
    categoria = db.get(Categoria, categoria_id)
    if not categoria:
        return RedirectResponse(url="/categorias/", status_code=303)

    usuario_id = request.session.get("usuario_id")
    query = db.query(Producto).filter(Producto.categoria_id == categoria_id, Producto.disponible.is_(True))
    if usuario_id is not None:
        query = query.filter(or_(Producto.vendedor_id.is_(None), Producto.vendedor_id != usuario_id))

    productos = query.order_by(Producto.id.desc()).all()
    return templates.TemplateResponse(request, "usuario/objetos.html", {
        "nombre": request.session.get("nombre", "Usuario"),
        "objetos": productos, "categoria_actual": categoria,
    })
