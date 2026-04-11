from datetime import datetime

from flask import jsonify
from static.helper.db import get_products_db

# --- Serials section ---
def api_process_warehouse_transfer(serial, past_owner):
    return {
        "success": True,
        "serial": serial,
        "new_owner": "מחסן",
        "previous_owner": past_owner,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def api_receive_warehouse_transfer(serial, new_owner):
    return {
        "success": True,
        "serial": serial,
        "new_owner": new_owner,
        "previous_owner": "מחסן",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def api_update_process_users_transfer(serial, past_owner, new_owner):
    return {
        "success": True,
        "serial": serial,
        "new_owner": new_owner,
        "previous_owner": past_owner,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def change_products_owner(city_name, owners):
    """
    city_name: שם העיר לסינון
    owners: מילון בצורה {product_id: new_owner_name}
    """
    conn = get_products_db()
    cursor = conn.cursor()

    try:
        for product_id, new_owner in owners.items():
            cursor.execute("""
                UPDATE products 
                SET owner = ? 
                WHERE id = ? AND city = ?
            """, (new_owner, product_id, city_name))

        conn.commit()
    except Exception as e:
        print(f"Error updating owners: {e}")
        conn.rollback()
    finally:
        conn.close()

def api_send_all_product_owners(city_name):
    owners = {} # getting the data from the server sorted by id (ILAN)

    change_products_owner(city_name, owners)

    return jsonify({
        'success': True,
        'city': city_name,
        'owners': list(owners),
        'count': len(owners)
    })

# --- Status section ---
def change_products_status(city_name, statuses):
    """
        city_name: שם העיר לסינון
        owners: מילון בצורה {product_id: new_owner_name}
        """
    conn = get_products_db()
    cursor = conn.cursor()

    try:
        for product_id, new_status in statuses.items():
            cursor.execute("""
                    UPDATE products 
                    SET status = ? 
                    WHERE id = ? AND city = ?
                """, (new_status, product_id, city_name))

        conn.commit()
    except Exception as e:
        print(f"Error updating owners: {e}")
        conn.rollback()
    finally:
        conn.close()

def api_send_all_product_status(city_name):
    """
        city_name: שם העיר לסינון
        statuses: מילון בצורה {product_id: new_status}
        לבן - WHITE
        שחור - BLACK
        תקול - RED
        חדש - GRAY
        """
    statuses = {} # getting the data from the server sorted by id (ILAN)

    change_products_status(city_name, statuses)

    return jsonify({
        'success': True,
        'city': city_name,
        'owners': list(statuses),
        'count': len(statuses)
    })

def api_update_product_status(serial, status):
    return {
        "success": True,
        "serial": serial,
        "status": status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def connect_to_tamir():
    pass
