"""Подготовка CSV без интерфейса: python -m scripts.prepare_data [--refresh]."""
import argparse
import logging
from services.pipeline import RoutePipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Загрузить маршрут по умолчанию и высоты из сети")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    bundle = RoutePipeline().load(force_network=args.refresh)
    logging.info("%s; %d samples; %.2f km", bundle.status, len(bundle.route), bundle.route.total_distance_m.iloc[-1] / 1000)
    logging.info("Метрики ML: %s", bundle.metrics)


if __name__ == "__main__":
    main()
