from abc import ABC, abstractmethod
from typing import List, Tuple

from pypdfium2 import PdfDocument
from src.image_to_text.data_preprocessing.util import extract_text
from tqdm import tqdm
import pandas as pd
from bs4 import BeautifulSoup
from datasets import load_dataset
from PIL.Image import Image
import torch
from sklearn.model_selection import train_test_split
from os import makedirs, path


class VitGPT2Dataset(ABC):

    def __init__(self, slide_path: str, dataset_path='/datasets/', max_target_length=128):
        self.extracted_test = None
        self.extracted_val = None
        self.extracted_train = None
        self.dataset = None
        self.train_metadata = None
        self.test_metadata = None
        self.val_metadata = None
        self.max_target_length = max_target_length
        self.dataset_path = dataset_path
        self.pdf = PdfDocument(slide_path)
        self.train_path = path.join(dataset_path, "train")
        self.test_path = path.join(dataset_path, "test")
        self.val_path = path.join(dataset_path, "val")

    @abstractmethod
    def build_metadata_csv(self, split_path: str, split_page_numbers: List[int]) -> pd.DataFrame:
        """
        This class builds the metadata.csv which defines the non-image features of the dataset.
        In this case, the file should contain two columns:
        1. file_name: Identifies the image which the label corresponds to
        2. question: The question, which acts as the label
        :return: None
        """
        raise NotImplementedError

    @staticmethod
    def _save_files_to_dir(dir_path: str, extracted_content: List[Tuple[int, str, str, Image]]):
        for slide_nr, _, _, slide_image in tqdm(extracted_content):
            slide_image.save(path.join(dir_path, f"slide_{slide_nr}.png"))

    @staticmethod
    def _extract_slide_page_numbers(split_extracted_content: List[tuple[int, str, str, Image]]) -> List[int]:
        return [page_nr for page_nr, _, _, _ in split_extracted_content]

    @staticmethod
    def preprocess(samples, feature_extractor, tokenizer, max_target_length):
        """ Preprocess the dataset to be used with vit-gpt2 """
        images = samples["image"]
        questions = samples["Question"]

        return {
            "labels": tokenizer(questions, padding="max_length", max_length=max_target_length).input_ids,
            "pixel_values": feature_extractor(images=images, return_tensors="np").pixel_values
        }

    def build_dataset(self, feature_extractor, tokenizer):
        extracted = extract_text(self.pdf.raw)

        self.extracted_train, val_test = train_test_split(extracted, test_size=0.4, train_size=0.6)
        self.extracted_val, self.extracted_test = train_test_split(val_test, test_size=0.5, train_size=0.5)

        makedirs(self.train_path, exist_ok=True)
        makedirs(self.val_path, exist_ok=True)
        makedirs(self.test_path, exist_ok=True)

        self.train_metadata = self.build_metadata_csv(
            split_path=self.train_path,
            split_page_numbers=self._extract_slide_page_numbers(self.extracted_train)
        )
        self.test_metadata = self.build_metadata_csv(
            split_path=self.test_path,
            split_page_numbers=self._extract_slide_page_numbers(self.extracted_test)
        )
        self.val_metadata = self.build_metadata_csv(
            split_path=self.val_path,
            split_page_numbers=self._extract_slide_page_numbers(self.extracted_val)
        )

        # filter unnecessary slides
        self.extracted_train = [t for t in self.extracted_train if t[0] in self.train_metadata["Page Number"].to_list()]
        self.extracted_test = [t for t in self.extracted_test if t[0] in self.test_metadata["Page Number"].to_list()]
        self.extracted_val = [t for t in self.extracted_val if t[0] in self.val_metadata["Page Number"].to_list()]

        self._save_files_to_dir(dir_path=self.train_path, extracted_content=self.extracted_train)
        self._save_files_to_dir(dir_path=self.test_path, extracted_content=self.extracted_test)
        self._save_files_to_dir(dir_path=self.val_path, extracted_content=self.extracted_val)

        dataset = load_dataset("imagefolder", data_dir=self.dataset_path)
        self.dataset = dataset.map(
            function=self.preprocess,
            batched=True,
            fn_kwargs={"max_target_length": self.max_target_length, "feature_extractor": feature_extractor,
                       "tokenizer": tokenizer},
            remove_columns=dataset['train'].column_names
        )


class VitGPT2GoldStandard(VitGPT2Dataset):

    def __init__(self, slide_path: str, dataset_path='datasets/gold_standard/', max_target_length=128):
        super().__init__(slide_path, dataset_path, max_target_length)

    def build_metadata_csv(self, split_path: str, split_page_numbers: List[int]) -> pd.DataFrame:
        df = pd.read_csv("datasets/gold_standard/Goldstandard.csv")
        df.drop(columns=["PDF-Name", "Marked for processing", "Includes Image Data", "Comment"], inplace=True)
        df.dropna(inplace=True)

        df["Page Number"] = df["Page Number"].astype(int)
        df["file_name"] = df["Page Number"].apply(lambda nr: f"slide_{int(nr)}.png")
        df = df[df["Page Number"].isin(split_page_numbers)]
        df.to_csv(path.join(split_path, "metadata.csv"), index=False)
        return df
