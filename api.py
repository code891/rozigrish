from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import logging
import sqlite3
import threading

# Добавляем родительскую директорию в путь для импорта модулей бота
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
# Временно убираем импорт для локального тестирования
# from utils.subscription_checker import check_user_subscriptions_api

app = Flask(__name__)
CORS(app)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread-local storage для базы данных
local_data = threading.local()

class Database:
    def __init__(self, db_name: str = 'giveaway.db'):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_user_balance(self, user_id: int) -> int:
        try:
            self.cursor.execute('SELECT tickets_balance FROM user_balance WHERE user_id = ?', (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except:
            return 0

    def get_active_giveaways(self) -> list:
        try:
            import json
            self.cursor.execute('''
                SELECT id, name, description, start_date, end_date, prize_places, 
                       prizes_json, photo_file_id, status, created_at 
                FROM giveaways 
                WHERE status = 'active' 
                ORDER BY created_at DESC
            ''')

            giveaways = []
            for row in self.cursor.fetchall():
                prizes = {}
                try:
                    if row[6]:  # prizes_json
                        prizes = json.loads(row[6])
                except:
                    pass

                giveaways.append({
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'start_date': row[3],
                    'end_date': row[4],
                    'prize_places': row[5],
                    'prizes': prizes,
                    'photo_file_id': row[7],
                    'status': row[8],
                    'is_active': 1 if row[8] == 'active' else 0,
                    'created_at': row[9]
                })
            return giveaways
        except:
            return []

    def get_giveaway_by_id(self, giveaway_id: int) -> dict:
        try:
            import json
            self.cursor.execute('''
                SELECT id, name, description, start_date, end_date, prize_places, 
                       prizes_json, photo_file_id, status, created_at 
                FROM giveaways WHERE id = ?
            ''', (giveaway_id,))

            row = self.cursor.fetchone()
            if not row:
                return None

            prizes = {}
            try:
                if row[6]:
                    prizes = json.loads(row[6])
            except:
                pass

            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'start_date': row[3],
                'end_date': row[4],
                'prize_places': row[5],
                'prizes': prizes,
                'photo_file_id': row[7],
                'status': row[8],
                'is_active': 1 if row[8] == 'active' else 0,
                'created_at': row[9]
            }
        except:
            return None

    def get_participants_count(self, giveaway_id: int) -> int:
        try:
            self.cursor.execute('SELECT COUNT(DISTINCT user_id) FROM tickets WHERE giveaway_id = ?', (giveaway_id,))
            return self.cursor.fetchone()[0]
        except:
            return 0

    def get_total_tickets_in_giveaway(self, giveaway_id: int) -> int:
        try:
            self.cursor.execute('SELECT COUNT(*) FROM tickets WHERE giveaway_id = ?', (giveaway_id,))
            return self.cursor.fetchone()[0]
        except:
            return 0

    def get_user_active_tickets_detailed(self, user_id: int) -> list:
        try:
            self.cursor.execute('''
                SELECT t.number, g.name as giveaway_name, g.id as giveaway_id, t.obtained_at
                FROM tickets t
                JOIN giveaways g ON t.giveaway_id = g.id
                WHERE t.user_id = ? AND g.status = 'active'
                ORDER BY g.name, t.number
            ''', (user_id,))

            tickets = []
            for row in self.cursor.fetchall():
                tickets.append({
                    'number': row[0],
                    'giveaway_name': row[1],
                    'giveaway_id': row[2],
                    'obtained_at': row[3]
                })
            return tickets
        except:
            return []

    def can_get_subscription_tickets(self, user_id: int) -> bool:
        return True  # Упрощенная версия для тестирования

    def get_days_until_next_tickets(self, user_id: int) -> int:
        return 0

    def get_referrals_count(self, user_id: int) -> int:
        try:
            self.cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,))
            return self.cursor.fetchone()[0]
        except:
            return 0

    def get_total_referral_rewards(self, user_id: int) -> int:
        return self.get_referrals_count(user_id)

    def add_participant(self, user_id: int, giveaway_id: int, tickets_count: int = 1) -> list:
        # Упрощенная версия
        return list(range(1, tickets_count + 1))

    def update_user_balance(self, user_id: int, amount: int) -> bool:
        try:
            current_balance = self.get_user_balance(user_id)
            new_balance = max(0, current_balance + amount)

            self.cursor.execute('''
                UPDATE user_balance SET tickets_balance = ? WHERE user_id = ?
            ''', (new_balance, user_id))

            if self.cursor.rowcount == 0:
                self.cursor.execute('''
                    INSERT INTO user_balance (user_id, tickets_balance, total_earned)
                    VALUES (?, ?, ?)
                ''', (user_id, new_balance, max(0, amount)))

            self.conn.commit()
            return True
        except:
            return False

    def get_user_past_giveaways(self, user_id: int) -> list:
        return []  # Заглушка

    def give_subscription_tickets(self, user_id: int) -> bool:
        return self.update_user_balance(user_id, 10)

    def get_statistics(self) -> dict:
        try:
            self.cursor.execute('SELECT COUNT(*) FROM users')
            users_count = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM giveaways WHERE status = 'active'")
            active_giveaways = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM giveaways WHERE status = 'completed'")
            completed_giveaways = self.cursor.fetchone()[0]

            self.cursor.execute('SELECT COUNT(*) FROM tickets')
            total_tickets = self.cursor.fetchone()[0]

            return {
                'users_count': users_count,
                'active_giveaways': active_giveaways,
                'completed_giveaways': completed_giveaways,
                'total_tickets': total_tickets
            }
        except:
            return {
                'users_count': 0,
                'active_giveaways': 0,
                'completed_giveaways': 0,
                'total_tickets': 0
            }

def is_admin(user_id):
    """Проверка админских прав"""
    try:
        return int(user_id) in config.ADMIN_IDS
    except:
        return False

def get_db():
    """Получает соединение с базой данных для текущего потока"""
    if not hasattr(local_data, 'db'):
        local_data.db = Database()
    return local_data.db

# Статические файлы
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# API endpoints

@app.route('/api/user/<int:user_id>')
def get_user_data(user_id):
    """Получение данных пользователя"""
    try:
        db = get_db()

        # Получаем пользователя через общий метод
        db.cursor.execute('SELECT user_id, username, full_name FROM users WHERE user_id = ?', (user_id,))
        user_row = db.cursor.fetchone()

        if not user_row:
            # Если пользователя нет, создаем временную запись для тестирования
            user = {
                'user_id': user_id,
                'username': f'user_{user_id}',
                'full_name': f'Тестовый пользователь {user_id}'
            }
        else:
            user = {
                'user_id': user_row[0],
                'username': user_row[1],
                'full_name': user_row[2]
            }

        balance = db.get_user_balance(user_id)
        active_tickets = db.get_user_active_tickets_detailed(user_id)
        active_giveaways_count = len(set(ticket['giveaway_id'] for ticket in active_tickets))

        can_get_tickets = db.can_get_subscription_tickets(user_id)
        days_until_next = db.get_days_until_next_tickets(user_id)

        referrals_count = db.get_referrals_count(user_id)
        total_referral_rewards = db.get_total_referral_rewards(user_id)

        # Используем реальных администраторов из конфигурации
        admin_ids = config.ADMIN_IDS

        return jsonify({
            'id': user['user_id'],
            'username': user['username'],
            'full_name': user['full_name'],
            'balance': balance,
            'active_giveaways_count': active_giveaways_count,
            'active_tickets_count': len(active_tickets),
            'can_get_subscription_tickets': can_get_tickets,
            'days_until_next_tickets': days_until_next,
            'referrals_count': referrals_count,
            'total_referral_rewards': total_referral_rewards,
            'is_admin': user_id in admin_ids
        })
    except Exception as e:
        logger.error(f"Ошибка получения данных пользователя {user_id}: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

@app.route('/api/giveaways')
def get_giveaways():
    """Получение списка активных розыгрышей"""
    try:
        db = get_db()
        giveaways = db.get_active_giveaways()
        result = []

        for giveaway in giveaways:
            participants_count = db.get_participants_count(giveaway['id'])
            total_tickets = db.get_total_tickets_in_giveaway(giveaway['id'])

            result.append({
                'id': giveaway['id'],
                'name': giveaway['name'],
                'description': giveaway['description'],
                'start_date': giveaway['start_date'],
                'end_date': giveaway['end_date'],
                'prize_places': giveaway['prize_places'],
                'prizes': giveaway.get('prizes', {}),
                'participants_count': participants_count,
                'total_tickets': total_tickets,
                'photo': giveaway.get('photo')
            })

        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка получения розыгрышей: {e}")
        return jsonify({'error': 'Ошибка получения розыгрышей'}), 500

@app.route('/api/giveaway/<int:giveaway_id>')
def get_giveaway(giveaway_id):
    """Получение детальной информации о розыгрыше"""
    try:
        db = get_db()
        giveaway = db.get_giveaway_by_id(giveaway_id)
        if not giveaway:
            return jsonify({'error': 'Розыгрыш не найден'}), 404

        participants_count = db.get_participants_count(giveaway_id)
        total_tickets = db.get_total_tickets_in_giveaway(giveaway_id)

        return jsonify({
            'id': giveaway['id'],
            'name': giveaway['name'],
            'description': giveaway['description'],
            'start_date': giveaway['start_date'],
            'end_date': giveaway['end_date'],
            'prize_places': giveaway['prize_places'],
            'prizes': giveaway.get('prizes', {}),
            'participants_count': participants_count,
            'total_tickets': total_tickets,
            'photo': giveaway.get('photo'),
            'is_active': giveaway['is_active']
        })
    except Exception as e:
        logger.error(f"Ошибка получения розыгрыша {giveaway_id}: {e}")
        return jsonify({'error': 'Ошибка получения розыгрыша'}), 500

@app.route('/api/participate', methods=['POST'])
def participate_in_giveaway():
    """Участие в розыгрыше"""
    try:
        db = get_db()
        data = request.get_json()
        user_id = data.get('user_id')
        giveaway_id = data.get('giveaway_id')
        ticket_count = data.get('ticket_count')

        if not all([user_id, giveaway_id, ticket_count]):
            return jsonify({'error': 'Не все параметры переданы'}), 400

        # Проверяем баланс пользователя
        user_balance = db.get_user_balance(user_id)
        if ticket_count <= 0 or ticket_count > user_balance:
            return jsonify({'error': f'Недостаточно билетов! У вас {user_balance} билетов'}), 400

        # Проверяем, что розыгрыш активен
        giveaway = db.get_giveaway_by_id(giveaway_id)
        if not giveaway or not giveaway['is_active']:
            return jsonify({'error': 'Розыгрыш не найден или завершён'}), 400

        # Добавляем участие
        db.add_participant(user_id, giveaway_id, ticket_count)
        db.update_user_balance(user_id, -ticket_count)

        return jsonify({
            'success': True,
            'message': f'Вы успешно участвуете в розыгрыше с {ticket_count} билетами!'
        })

    except Exception as e:
        logger.error(f"Ошибка участия в розыгрыше: {e}")
        return jsonify({'error': 'Ошибка при участии в розыгрыше'}), 500

@app.route('/api/user/<int:user_id>/tickets')
def get_user_tickets(user_id):
    """Получение билетов пользователя"""
    try:
        db = get_db()
        tickets = db.get_user_active_tickets_detailed(user_id)

        # Группируем билеты по розыгрышам
        giveaway_tickets = {}
        for ticket in tickets:
            giveaway_name = ticket['giveaway_name']
            if giveaway_name not in giveaway_tickets:
                giveaway_tickets[giveaway_name] = {
                    'giveaway_id': ticket['giveaway_id'],
                    'giveaway_name': giveaway_name,
                    'tickets': []
                }
            giveaway_tickets[giveaway_name]['tickets'].append(ticket['number'])

        return jsonify(list(giveaway_tickets.values()))
    except Exception as e:
        logger.error(f"Ошибка получения билетов пользователя {user_id}: {e}")
        return jsonify({'error': 'Ошибка получения билетов'}), 500

@app.route('/api/user/<int:user_id>/history')
def get_user_history(user_id):
    """Получение истории участий пользователя"""
    try:
        db = get_db()
        history = db.get_user_past_giveaways(user_id)
        return jsonify(history[:20])  # Возвращаем последние 20 участий
    except Exception as e:
        logger.error(f"Ошибка получения истории пользователя {user_id}: {e}")
        return jsonify({'error': 'Ошибка получения истории'}), 500

@app.route('/api/check-subscriptions', methods=['POST'])
def check_subscriptions():
    """Проверка подписок и выдача билетов"""
    try:
        db = get_db()
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'user_id не передан'}), 400

        # Проверяем, может ли пользователь получить билеты
        if not db.can_get_subscription_tickets(user_id):
            days_left = db.get_days_until_next_tickets(user_id)
            return jsonify({
                'success': False,
                'error': f'Следующие билеты можно получить через {days_left} дней'
            }), 400

        # Здесь должна быть проверка подписок через Telegram API
        # Пока что считаем, что пользователь подписан
        is_subscribed = True

        if not is_subscribed:
            return jsonify({
                'success': False,
                'error': 'Вы не подписаны на все каналы'
            }), 400

        # Выдаем билеты
        if db.give_subscription_tickets(user_id):
            return jsonify({
                'success': True,
                'message': 'Вы получили 10 билетов за подписки! (действительны 15 дней)'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка при выдаче билетов'
            }), 500

    except Exception as e:
        logger.error(f"Ошибка проверки подписок: {e}")
        return jsonify({'error': 'Ошибка при проверке подписок'}), 500

@app.route('/api/admin/stats')
def get_admin_stats():
    """Получение статистики для админов"""
    try:
        db = get_db()
        stats = db.get_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return jsonify({'error': 'Ошибка получения статистики'}), 500

@app.route('/api/admin/create-giveaway', methods=['POST'])
def create_giveaway():
    """Создание нового розыгрыша через веб-интерфейс"""
    try:
        db = get_db()
        data = request.get_json()

        # Проверяем права администратора
        admin_id = data.get('admin_id')
        if not admin_id or admin_id not in config.ADMIN_IDS:
            return jsonify({'success': False, 'error': 'Нет прав администратора'}), 403

        # Извлекаем данные
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        start_date = data.get('start_date', '').strip()
        end_date = data.get('end_date', '').strip()
        end_time = data.get('end_time', '23:59')
        auto_complete = data.get('auto_complete', False)
        prizes = data.get('prizes', {})

        # Валидация данных
        if not name:
            return jsonify({'success': False, 'error': 'Название обязательно'}), 400

        if not description:
            return jsonify({'success': False, 'error': 'Описание обязательно'}), 400

        if not start_date or not end_date:
            return jsonify({'success': False, 'error': 'Даты начала и окончания обязательны'}), 400

        if not prizes:
            return jsonify({'success': False, 'error': 'Нужен хотя бы один приз'}), 400

        # Проверяем даты
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            if end_dt <= start_dt:
                return jsonify({'success': False, 'error': 'Дата окончания должна быть позже даты начала'}), 400

        except ValueError:
            return jsonify({'success': False, 'error': 'Неверный формат даты'}), 400

        # Конвертируем даты в нужный формат
        start_date_formatted = start_dt.strftime('%d.%m.%Y')
        end_date_formatted = end_dt.strftime('%d.%m.%Y')

        # Создаем розыгрыш
        giveaway_id = db.create_giveaway(
            name=name,
            description=description,
            start_date=start_date_formatted,
            end_date=end_date_formatted,
            prize_places=len(prizes),
            prizes=prizes,
            photo_file_id=None,
            end_time=end_time,
            auto_complete=auto_complete
        )

        if giveaway_id:
            logger.info(f"✅ Админ {admin_id} создал розыгрыш '{name}' через веб-интерфейс")
            return jsonify({
                'success': True,
                'message': 'Розыгрыш успешно создан',
                'giveaway_id': giveaway_id
            })
        else:
            return jsonify({'success': False, 'error': 'Ошибка создания розыгрыша в базе данных'}), 500

    except Exception as e:
        logger.error(f"Ошибка создания розыгрыша через API: {e}")
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)