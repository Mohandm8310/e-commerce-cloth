from flask_login import login_user
from app.extensions import db
from app.models.product import Product, ProductVariant
from app.models.analytics import AdminAuditLog


def test_unauthorized_admin_access_blocked(client):
    # Unauthenticated visitor attempting to access admin dashboard
    res = client.get('/admin/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/admin/login' in res.headers['Location']


def test_customer_user_forbidden_from_admin(client, customer_user):
    # Customer user attempting to access admin dashboard must receive 403 Forbidden
    with client.session_transaction() as sess:
        sess['_user_id'] = str(customer_user.id)

    res = client.get('/admin/dashboard')
    assert res.status_code == 403


def test_admin_login_and_dashboard_access(client, admin_user):
    res = client.post('/admin/login', data={
        'email': 'admin_test@stylesphere.com',
        'password': 'AdminTest@123'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b'Executive Dashboard' in res.data or b'StyleSphere' in res.data


def test_admin_product_crud_and_undo_restore(client, admin_user, sample_product):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)

    # 1. Soft-delete the product
    del_res = client.post(f'/admin/products/{sample_product.id}/delete', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert del_res.status_code == 200
    del_json = del_res.get_json()
    assert del_json['success'] is True
    assert 'undo_url' in del_json

    # Check product state in DB
    prod = Product.query.get(sample_product.id)
    assert prod.is_deleted is True
    assert prod.deleted_at is not None

    # Check audit log recorded
    log = AdminAuditLog.query.filter_by(action='SOFT_DELETE_PRODUCT', entity_id=str(prod.id)).first()
    assert log is not None

    # 2. Undo / restore product
    restore_res = client.post(del_json['undo_url'], headers={'X-Requested-With': 'XMLHttpRequest'})
    assert restore_res.status_code == 200
    res_json = restore_res.get_json()
    assert res_json['success'] is True

    # Check product restored in DB
    db.session.refresh(prod)
    assert prod.is_deleted is False
    assert prod.deleted_at is None
    assert prod.is_active is True

    # Check restore audit log recorded
    restore_log = AdminAuditLog.query.filter_by(action='RESTORE_PRODUCT', entity_id=str(prod.id)).first()
    assert restore_log is not None
