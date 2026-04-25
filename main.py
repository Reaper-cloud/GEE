import ee

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
months = [5, 6, 7, 8, 9, 10, 11]                     # июль
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
# 5. Основной цикл
# ---------------------------------------------------------------------
for month in months:
    start_date = ee.Date.fromYMD(year, month, 1)
    end_date = start_date.advance(1, 'month')
    print(f'Обработка {year}-{month:02d} ...')

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

        if lst_coll.size().getInfo() > 0:
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
            print(f'  Запущен экспорт: {desc}')
        else:
            print(f'  Нет изображений для {name}')

    # ---- Суточные средние Terra (из 8-дневных композитов) ----
    terra_8day_coll = ee.ImageCollection('MODIS/061/MOD11A2') \
        .filterDate(start_date, end_date) \
        .filterBounds(lake_geom) \
        .select(['LST_Day_1km', 'LST_Night_1km'])

    def calc_daily_mean(img):
        day_c = dn_to_celsius_modis(img, 'LST_Day_1km')
        night_c = dn_to_celsius_modis(img, 'LST_Night_1km')
        daily = day_c.add(night_c).divide(2).rename('daily_mean')
        # Оставляем пиксели, где есть и день, и ночь
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
        print(f'  Запущен экспорт: {desc_daily}')
    else:
        print('  Нет данных для Terra_DailyMean')

print('Все задачи экспорта отправлены.')