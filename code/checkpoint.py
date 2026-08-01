import abc
import json
import logging
from typing import Any, Callable, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class StateStore(abc.ABC):
    """Abstract base class for checkpoint state storage."""
    @abc.abstractmethod
    def save(self, run_id: str, step_name: str, state: Dict[str, Any]) -> None:
        pass
    
    @abc.abstractmethod
    def load(self, run_id: str) -> Optional[Dict[str, Any]]:
        pass
    
    @abc.abstractmethod
    def get_last_completed_step(self, run_id: str) -> Optional[str]:
        pass


class FileStateStore(StateStore):
    """Local JSON file-based state store for checkpoints."""
    def __init__(self, directory: str = ".checkpoints"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        
    def _get_path(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.json"
        
    def save(self, run_id: str, step_name: str, state: Dict[str, Any]) -> None:
        path = self._get_path(run_id)
        data = {
            "last_step": step_name,
            "state": state
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            
    def load(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_path(run_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
            return data.get("state")
            
    def get_last_completed_step(self, run_id: str) -> Optional[str]:
        path = self._get_path(run_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
            return data.get("last_step")


class CheckpointRunner:
    """
    Executes a pipeline of steps sequentially. 
    If it fails, it can be re-run and will resume from the last completed step.
    """
    def __init__(self, run_id: str, store: StateStore):
        self.run_id = run_id
        self.store = store
        self.steps = []
        
    def add_step(self, name: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """
        Add a step to the pipeline.
        func should take a state dictionary and return an updated state dictionary.
        """
        self.steps.append((name, func))
        
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the pipeline, skipping steps that have already completed."""
        state = initial_state
        last_step = self.store.get_last_completed_step(self.run_id)
        
        # Load state if we are resuming
        if last_step:
            loaded_state = self.store.load(self.run_id)
            if loaded_state:
                state = loaded_state
                logger.info(f"Resuming run '{self.run_id}' from state after step '{last_step}'.")
        
        start_idx = 0
        if last_step:
            for i, (name, _) in enumerate(self.steps):
                if name == last_step:
                    start_idx = i + 1
                    break
        
        for name, func in self.steps[start_idx:]:
            logger.info(f"Running step: {name}")
            state = func(state)
            self.store.save(self.run_id, name, state)
            logger.info(f"Saved checkpoint for step: {name}")
            
        return state
