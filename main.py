import ee
import time
import logging

# Настройка логов для мониторинга
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Аутентификация и инициализация
ee.Authenticate()
ee.Initialize(project="proud-archery-488609-q6")

# ---------------------------------------------------------------------
# 1. Геометрия озера Байкал
# ---------------------------------------------------------------------
baikal_fc = ee.FeatureCollection('users/reaper/baik')
lake_geom = baikal_fc.geometry()

# ---------------------------------------------------------------------
# 2. Параметры
# ---------------------------------------------------------------------
year = 2014
months = [5, 6, 7, 8, 9, 10, 11]                     # май – ноябрь (исключены янв-апр, дек)
scale = 1000
drive_folder = 'EarthEngineExports'

# ---------------------------------------------------------------------
# 3. Коллекции (8-дневные MODIS + VIIRS)
# ---------------------------------------------------------------------
collections = {
    'Terra_8day_Day':     ('MODIS/061/MOD11A2', 'LST_Day_1km'),
    'Terra_8day_Night':   ('MODIS/061/MOD11A2', 'LST_Night_1km'),
    'Aqua_8day_Day':      ('MODIS/061/MYD11A2', 'LST_Day_1km'),
    'Aqua_8day_Night':    ('MODIS/061/MYD11A2', 'LST_Night_1km'),
    'VIIRS_Day':          ('NASA/VIIRS/002/VNP21A1D', 'LST_1KM'),
    'VIIRS_Night':        ('NASA/VIIRS/002/VNP21A1N', 'LST_1KM')
}

# ---------------------------------------------------------------------
# 4. Преобразование DN в °C
# ---------------------------------------------------------------------
def dn_to_celsius_viirs(image, band):
    return image.select(band).add(-273.15).float()

def dn_to_celsius_modis(image, band):
    return image.select(band).multiply(0.02).add(-273.15).float()

# ---------------------------------------------------------------------
# 5. Функция ожидания завершения всех задач
# ---------------------------------------------------------------------
def wait_for_tasks(tasks, check_interval=300):
    """
    Ожидает завершения (COMPLETED, FAILED, CANCELLED) всех задач из списка.
    Проверка статуса выполняется каждые check_interval секунд.
    """
    if not tasks:
        logging.info("Нет задач для ожидания.")
        return

    logging.info(f"Ожидание завершения {len(tasks)} задач...")
    while True:
        all_done = True
        for task in tasks:
            status = task.status()
            state = status['state']
            if state not in ['COMPLETED', 'FAILED', 'CANCELLED']:
                all_done = False
                logging.debug(f"Задача {task.id} ещё выполняется (статус: {state})")
                break
        if all_done:
            # Вывод итогового статуса
            completed = sum(1 for t in tasks if t.status()['state'] == 'COMPLETED')
            failed = sum(1 for t in tasks if t.status()['state'] == 'FAILED')
            cancelled = sum(1 for t in tasks if t.status()['state'] == 'CANCELLED')
            logging.info(f"Все задачи завершены. Успешно: {completed}, ошибок: {failed}, отменено: {cancelled}")
            break
        logging.info(f"Не все задачи завершены. Следующая проверка через {check_interval} секунд.")
        time.sleep(check_interval)

# ---------------------------------------------------------------------
# 6. Основной цикл по месяцам с таймером
# ---------------------------------------------------------------------
for month in months:
    start_date = ee.Date.fromYMD(year, month, 1)
    end_date = start_date.advance(1, 'month')
    logging.info(f'Обработка {year}-{month:02d} ...')

    # Список задач для текущего месяца
    current_tasks = []

    # ---- Экспорт 8-дневных композитов и VIIRS ----
    for name, (coll_id, band) in collections.items():
        coll = ee.ImageCollection(coll_id) \
            .filterDate(start_date, end_date) \
            .filterBounds(lake_geom)

        convert_func = dn_to_celsius_viirs if 'VIIRS' in name else dn_to_celsius_modis

        def process(img):
            lst = convert_func(img, band)
            return lst.copyProperties(img, ['system:time_start'])

        lst_coll = coll.map(process)

        # Проверка наличия изображений
        coll_size = lst_coll.size().getInfo()
        if coll_size > 0:
            mean_img = lst_coll.mean().clip(lake_geom)

            desc = f'{name}_{year}_{month:02d}'
            task = ee.batch.Export.image.toDrive(
                image=mean_img,
                description=desc,
                folder=drive_folder,
                fileNamePrefix=desc,
                region=lake_geom,
                scale=scale,
                crs='EPSG:4326',
                maxPixels=1e13
            )
            task.start()
            current_tasks.append(task)
            logging.info(f'  Запущен экспорт: {desc}')
        else:
            logging.warning(f'  Нет изображений для {name}')

    # ---- Суточные средние Terra (из 8-дневных композитов) ----
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
        monthly_daily_mean = daily_means.mean().clip(lake_geom)

        desc_daily = f'Terra_DailyMean_8day_{year}_{month:02d}'
        task_daily = ee.batch.Export.image.toDrive(
            image=monthly_daily_mean,
            description=desc_daily,
            folder=drive_folder,
            fileNamePrefix=desc_daily,
            region=lake_geom,
            scale=scale,
            crs='EPSG:4326',
            maxPixels=1e13
        )
        task_daily.start()
        current_tasks.append(task_daily)
        logging.info(f'  Запущен экспорт: {desc_daily}')
    else:
        logging.warning('  Нет данных для Terra_DailyMean')

    # ---- Ожидание завершения всех задач для текущего месяца ----
    wait_for_tasks(current_tasks, check_interval=300)

    # ---- Задержка на один месяц (30 дней) перед следующим месяцем ----
    # (Пропускаем задержку после последнего месяца, чтобы завершить скрипт)
    if month != months[-1]:
        delay_seconds = 30 * 24 * 3600  # 30 дней
        logging.info(f'Ожидание {delay_seconds / 86400:.0f} дней перед обработкой следующего месяца...')
        time.sleep(delay_seconds)

logging.info('Все месяцы обработаны. Скрипт завершён.'))