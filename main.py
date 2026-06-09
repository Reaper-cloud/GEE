# export_to_asset_service_account.py (исправленный – без папки /exports)
import ee
import time
import logging

# ========== 1. Авторизация сервисного аккаунта ==========
SERVICE_ACCOUNT = "reaper@proud-archery-488609-q6.iam.gserviceaccount.com"
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC8FJxcDo+n/nPG
WkX+NAzLdUbTtOTMdeipYgUR3QcjnyujlH7Ps/0uIg21vIT8oHUpF1MULNDWOxAW
QHXCi+sS334eZJwBwlJ3dOAklpo3t5WPnCZ+JLw+SmDVXsPFoD4D2bpcF2/nmFOt
7yNQcLe8zAaGxGM40iELe4Qqih4XhxEAgx2UeMp1FKUprH+cIC0+VqnsQUCFIn/j
Z8GR1fOZNVgeiQ+IKpooy8i8go3rCDyFuGDWFuDuVQrNMUAlbrhvW0dhVF12pctP
mI71giZb+71xI/5qc0f3pJxPm9EpT1QGisJhqTanw53aXG31SXgqA5cKe6Wf4c/5
5ayR8hGdAgMBAAECggEAE26wug0yGAohBaMxnKJdmQ7orrp/skVTcN7FBdO3p11M
ebX/xS+ETuYrUvXjqqNcf46eoZTAzgWjs5zc3ektdFF9mx/Lg54Dfb6oYvdhfzS7
Ye9hBcL/ZRMzvo/wO8TC64xtJhMw13WkXbH5zNeckEfnO7jiRI5nZiOQpAGJuuXm
uv2C8Wada9IMwi2awqcDMiNodMvGqmjuF3xLadhJMdEGbiBGkzjn0kiqHpDrCx/1
T5LLiN9b/F2rL419kzzpCA/jukCfHHWJWH3ofITS3+xux26UZ2MaAtVrDu79Vq08
IAKwvmUDSYHjJwyEMun58Kise+0QvLcaDYcDarRA8QKBgQD2syDKH8AqFX9V6Z+0
zp1n6edpbEakpRJt61HL+HT4oDUpjFOkDG/4DC/y1lQU4UIw/oD3X8L5xyOidv5F
c+8/M62pPXTTcaE5rPNCxq0j0h2+1XgB+5kWLzzEjsaTN1BAtA1xpag/lsioektC
G9txzeL3LoQafQb5W3Xm7FhwTQKBgQDDK8FRgLQsBmqwUfwtquXSOclGrHMyCYiI
SfrWNGYEQoRzEk9A1lMWgxW6iYGFXv2FB2f9YBnucPoOagDXrO7tdkgpUiUllR9r
TrlCrWEDTeJkM0rUGo/GghjPwNTHKyrHPtY/GoyUQdk89w1QqDBqII7wiRBiy4bo
Biqzca9OkQKBgQCGLI6c3//n46FJ3LKb5/P8XF8cG2OgkJchaWcnhI452wiO/F9R
TeJoCljZvnAkmw8hDoqeAFtO9lwPNKC+rXtl6Hl/Hom3pomFkOcNXnk0jkbXT8rh
aTGtuytVzEF8OA1R45ucP/jt/NhNqZXc8sG7d7sFrSr0LSPp4zCQ0+KV0QKBgARa
l4dv7ZUF159zVMLYCyRzcZAIDNHS8J7Jt7TLmnMB4N6ITAhQP65C4ls08hS9l749
+g3m9O0izBFCQB6PlwzpFJcHZBjAiODl8rAQGhfuxtwhYMv2g7qT8GXCEX0X825a
coEZ4IT2Kxh3Em74MYxMiaPICvuJOss2SAGUyaphAoGBAKtioWLRknYhGxHhE6vX
0OGEnBjgzdFJZqj9LvxJ8EDQIc3lKDQXykdbJk1Dr6z617GdjV/+yzi+q2gU5PX7
LhkxvSirG67GHPKh3E7y2vuiFSe4omTLnzTFw0L/AP1U5Mh/aPVMMcBGjCXE40wh
HUs45iN176qtktqPaMzh02LG
-----END PRIVATE KEY-----"""


credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, key_data=PRIVATE_KEY)
ee.Initialize(credentials, project="proud-archery-488609-q6")

# ========== 2. Логи ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ========== 3. Геометрия из вашего ассета ==========
try:
    baikal_fc = ee.FeatureCollection('users/reaper/baik')
    count = baikal_fc.size().getInfo()
    if count == 0:
        raise ValueError("FeatureCollection пуста")
    lake_geom = baikal_fc.geometry()
    mask = ee.Image.constant(1).clip(lake_geom)
    logging.info(f"Ассет 'users/reaper/baik' загружен, {count} объектов.")
except Exception as e:
    logging.error(f"Не удалось загрузить ассет: {e}")
    logging.error("Убедитесь, что вы расшарили 'users/reaper/baik' для сервисного аккаунта")
    exit(1)

# ========== 4. Параметры ==========
year = 2014
months = [5, 6, 7, 8, 9, 10, 11]   # май–ноябрь
scale = 1000

# ========== 5. Коллекции и функции ==========
collections = {
    'Terra_8day_Day':     ('MODIS/061/MOD11A2', 'LST_Day_1km'),
    'Terra_8day_Night':   ('MODIS/061/MOD11A2', 'LST_Night_1km'),
    'Aqua_8day_Day':      ('MODIS/061/MYD11A2', 'LST_Day_1km'),
    'Aqua_8day_Night':    ('MODIS/061/MYD11A2', 'LST_Night_1km'),
    'VIIRS_Day':          ('NASA/VIIRS/002/VNP21A1D', 'LST_1KM'),
    'VIIRS_Night':        ('NASA/VIIRS/002/VNP21A1N', 'LST_1KM')
}

def dn_to_celsius_viirs(img, band):
    return img.select(band).add(-273.15).float()

def dn_to_celsius_modis(img, band):
    return img.select(band).multiply(0.02).add(-273.15).float()

def wait_for_tasks(tasks, check_interval=300):
    if not tasks:
        logging.info("Нет задач для ожидания.")
        return
    logging.info(f"Ожидание завершения {len(tasks)} задач...")
    while True:
        states = [t.status()['state'] for t in tasks]
        if all(s in ('COMPLETED','FAILED','CANCELLED') for s in states):
            completed = sum(1 for s in states if s == 'COMPLETED')
            logging.info(f"Все задачи завершены. Успешно: {completed} из {len(tasks)}")
            break
        logging.info(f"Не все задачи завершены. Следующая проверка через {check_interval} сек.")
        time.sleep(check_interval)

# ========== 6. Список ассетов ==========
asset_ids = []

# ========== 7. Цикл по месяцам ==========
for month in months:
    start_date = ee.Date.fromYMD(year, month, 1)
    end_date = start_date.advance(1, 'month')
    logging.info(f'Обработка {year}-{month:02d} ...')

    current_tasks = []

    # ---- 8-дневные композиты и VIIRS ----
    for name, (coll_id, band) in collections.items():
        coll = ee.ImageCollection(coll_id) \
            .filterDate(start_date, end_date) \
            .filterBounds(lake_geom)

        convert = dn_to_celsius_viirs if 'VIIRS' in name else dn_to_celsius_modis

        def process(img):
            lst = convert(img, band)
            return lst.copyProperties(img, ['system:time_start'])

        lst_coll = coll.map(process)
        coll_size = lst_coll.size().getInfo()

        if coll_size > 0:
            mean_img = lst_coll.mean().updateMask(mask)
            desc = f'{name}_{year}_{month:02d}'
            # Прямой путь в корень assets проекта
            asset_id = f'projects/proud-archery-488609-q6/assets/{desc}'
            asset_ids.append(asset_id)

            task = ee.batch.Export.image.toAsset(
                image=mean_img,
                description=desc,
                assetId=asset_id,
                region=lake_geom,
                scale=scale,
                crs='EPSG:4326',
                maxPixels=1e13,
                overwrite=True
            )
            task.start()
            current_tasks.append(task)
            logging.info(f'  Запущен экспорт в Asset: {asset_id}')
        else:
            logging.warning(f'  Нет изображений для {name}')

    # ---- Суточные средние Terra ----
    terra_8day_coll = ee.ImageCollection('MODIS/061/MOD11A2') \
        .filterDate(start_date, end_date) \
        .filterBounds(lake_geom) \
        .select(['LST_Day_1km', 'LST_Night_1km'])

    def calc_daily_mean(img):
        day_c = dn_to_celsius_modis(img, 'LST_Day_1km')
        night_c = dn_to_celsius_modis(img, 'LST_Night_1km')
        daily = day_c.add(night_c).divide(2).rename('daily_mean')
        daily = daily.updateMask(day_c.mask().And(night_c.mask()))
        return daily.copyProperties(img, ['system:time_start'])

    daily_means = terra_8day_coll.map(calc_daily_mean)

    if daily_means.size().getInfo() > 0:
        monthly_daily_mean = daily_means.mean().updateMask(mask)
        desc_daily = f'Terra_DailyMean_8day_{year}_{month:02d}'
        asset_id_daily = f'projects/proud-archery-488609-q6/assets/{desc_daily}'
        asset_ids.append(asset_id_daily)

        task_daily = ee.batch.Export.image.toAsset(
            image=monthly_daily_mean,
            description=desc_daily,
            assetId=asset_id_daily,
            region=lake_geom,
            scale=scale,
            crs='EPSG:4326',
            maxPixels=1e13,
            overwrite=True
        )
        task_daily.start()
        current_tasks.append(task_daily)
        logging.info(f'  Запущен экспорт в Asset: {asset_id_daily}')
    else:
        logging.warning('  Нет данных для Terra_DailyMean')

    # ---- Ожидание конца месяца ----
    wait_for_tasks(current_tasks, check_interval=300)

    # ---- Пауза 30 дней (кроме последнего месяца) ----
    if month != months[-1]:
        logging.info('Ожидание 30 дней перед следующим месяцем...')
        time.sleep(30 * 24 * 3600)

# ========== 8. Сохраняем список ассетов ==========
with open('asset_list.txt', 'w') as f:
    for aid in asset_ids:
        f.write(aid + '\n')

logging.info(f'Экспорт в Asset завершён. Список ассетов сохранён в asset_list.txt (всего {len(asset_ids)}).')